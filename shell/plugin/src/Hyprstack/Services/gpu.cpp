#include "gpu.hpp"

#include <qdir.h>
#include <qdiriterator.h>
#include <qfile.h>
#include <QTimer>
#include <memory>
#include <qregularexpression.h>

#include "config/rootnodes.hpp"
#include "config/serviceconfig.hpp"

namespace hyprstack::services {

using Qt::StringLiterals::operator""_s;

namespace {

QStringList gpuBusyFiles() {
    static const QRegularExpression k_cardRe(u"^card\\d+$"_s);

    QStringList files;
    QDirIterator it(u"/sys/class/drm"_s, QDir::Dirs | QDir::NoDotAndDotDot);
    while (it.hasNext()) {
        const QString path = it.next();
        if (!k_cardRe.match(it.fileName()).hasMatch()) {
            continue;
        }
        const QString busy = path + u"/device/gpu_busy_percent"_s;
        if (QFile::exists(busy)) {
            files << busy;
        }
    }
    return files;
}

QString cleanName(QString s) {
    static const QRegularExpression k_noise(u"\\(R\\)|\\(TM\\)|Graphics"_s, QRegularExpression::CaseInsensitiveOption);
    static const QRegularExpression k_spaces(u"\\s+"_s);
    s.replace(k_noise, {});
    s.replace(k_spaces, u" "_s);
    return s.trimmed();
}

QString parseNvidiaName(const QByteArray& out) {
    const QString first = QString::fromUtf8(out).split(u'\n').value(0).trimmed();
    return first.isEmpty() ? QString() : cleanName(first);
}

QString parseGlxinfoName(const QByteArray& out) {
    const QStringList lines = QString::fromUtf8(out).split(u'\n');
    for (const QString& line : lines) {
        const qsizetype idx = line.indexOf(u"Device:"_s);
        if (idx < 0) {
            continue;
        }

        QString rest = line.mid(idx + 7);
        const qsizetype paren = rest.indexOf(u'(');
        if (paren >= 0) {
            rest = rest.left(paren);
        }

        const QString cleaned = cleanName(rest);
        if (!cleaned.isEmpty()) {
            return cleaned;
        }
    }

    return {};
}

QString parseLspciName(const QByteArray& out) {
    static const QRegularExpression k_lineRe(u"vga|3d controller|display"_s, QRegularExpression::CaseInsensitiveOption);

    const QStringList lines = QString::fromUtf8(out).split(u'\n');
    QString match;
    for (const QString& line : lines) {
        if (k_lineRe.match(line).hasMatch()) {
            match = line;
            break;
        }
    }

    if (match.isEmpty()) {
        return {};
    }

    static const QRegularExpression k_bracketRe(u"\\[([^\\]]+)\\][^\\[]*$"_s);
    const auto bracket = k_bracketRe.match(match);
    if (bracket.hasMatch()) {
        return cleanName(bracket.captured(1));
    }

    // Split on a colon followed by whitespace so the PCI slot ("00:02.0") is not
    // mistaken for the class/name separator ("controller: Device").
    static const QRegularExpression k_colonRe(u":\\s+(.+)"_s);
    const auto colon = k_colonRe.match(match);
    if (colon.hasMatch()) {
        return cleanName(colon.captured(1));
    }

    return {};
}

struct NameSource {
    QString program;
    QStringList args;
    QString (*parse)(const QByteArray&);
};

// Name probes in priority order; the first non-empty result wins. Which of them run
// depends on the resolved type.
const std::array<NameSource, 3>& nameSources() {
    static const std::array<NameSource, 3> k_sources = {
        {
            {
                .program = u"nvidia-smi"_s,
                .args = { u"--query-gpu=name"_s, u"--format=csv,noheader"_s },
                .parse = &parseNvidiaName,
            },
            {
                .program = u"glxinfo"_s,
                .args = { u"-B"_s },
                .parse = &parseGlxinfoName,
            },
            {
                .program = u"lspci"_s,
                .args = {},
                .parse = &parseLspciName,
            },
        },
    };
    return k_sources;
}

// Indices within nameSources(): nvidia-smi, then the driver-agnostic probes.
constexpr int k_nvidiaSource = 0;
constexpr int k_firstGenericSource = 1;

} // namespace

Gpu::Gpu(QObject* parent)
    : TickingService(parent), m_metrics(this) {
    m_busyFiles = gpuBusyFiles();

    const auto* svc = hyprstack::config::ConfigSingleton::instance()->services();
    m_userType = svc->gpuType();
    QObject::connect(svc, &hyprstack::config::ServiceConfig::gpuTypeChanged, this, [this, svc] {
        const GpuType value = svc->gpuType();
        if (value == m_userType) {
            return;
        }
        m_userType = value;
        resolveGpu();
    });

    resolveGpu();
}

GpuType Gpu::type() const {
    return m_type;
}

Gpu::~Gpu() {
    m_metrics.reset();
    for(auto* process:findChildren<QProcess*>(QString(),Qt::FindDirectChildrenOnly)) {
        process->disconnect(this);process->setParent(nullptr);process->kill();
        if(process->state()==QProcess::NotRunning)process->deleteLater();
        else connect(process,&QProcess::finished,process,&QObject::deleteLater);
    }
}

QString Gpu::name() const {
    return m_name;
}

bool Gpu::detecting() const {
    return m_detecting;
}

qreal Gpu::percentage() const {
    return m_percentage;
}

qreal Gpu::temperature() const {
    return m_temperature;
}

void Gpu::setType(GpuType value) {
    if (value == m_type) {
        return;
    }
    m_type = value;
    if (m_type == GpuType::None) {
        resetUsage();
    }
    emit typeChanged();
}

void Gpu::setName(QString value) {
    if (value == m_name) {
        return;
    }
    m_name = std::move(value);
    emit nameChanged();
}

void Gpu::setDetecting(bool value) {
    if (value == m_detecting) {
        return;
    }
    m_detecting = value;
    emit detectingChanged();
}

void Gpu::tick() {
    if (m_type == GpuType::Generic) {
        startGpuUsage();
    } else if (m_type == GpuType::Nvidia) {
        startGpuUsage();
    } else {
        resetUsage();
    }
}

void Gpu::resolveGpu() {
    // Supersede any chain still in flight so its callbacks cannot write stale state
    const int generation = ++m_generation;
    ++m_usageGeneration;m_metrics.reset();m_nvidiaQuerying=false;

    if (m_userType != GpuType::Auto) {
        setType(m_userType);
    }

    if (m_userType == GpuType::None) {
        setName({});
        setDetecting(false);
        return;
    }

    setName({});
    setDetecting(true);
    tryNameSource(m_userType == GpuType::Generic ? k_firstGenericSource : k_nvidiaSource, generation);
}

int Gpu::probeEnd() const {
    return m_userType == GpuType::Nvidia ? k_firstGenericSource : static_cast<int>(nameSources().size());
}

void Gpu::tryNameSource(int index, int generation) {
    const NameSource& src = nameSources().at(static_cast<std::size_t>(index));
    runProcess(src.program, src.args, [this, index, generation, parse = src.parse](const QByteArray& out) {
        finishNameSource(index, generation, parse(out));
    });
}

void Gpu::finishNameSource(int index, int generation, QString name) {
    if (generation != m_generation) {
        return; // superseded by a newer resolution
    }

    // Under Auto the NVIDIA name probe doubles as the type probe: a non-empty result
    // means an NVIDIA GPU is present and queryable.
    if (m_userType == GpuType::Auto && index == k_nvidiaSource) {
        if (!name.isEmpty())
            setType(GpuType::Nvidia);
        else
            setType(m_busyFiles.isEmpty() ? GpuType::None : GpuType::Generic);

        if (m_type == GpuType::None) {
            setName({});
            setDetecting(false);
            return;
        }
    }

    if (!name.isEmpty()) {
        setName(std::move(name));
        setDetecting(false);
        return;
    }

    // Fall through to the next applicable source
    const int next = index + 1;
    if (next < probeEnd()) {
        tryNameSource(next, generation);
    } else {
        setName({});
        setDetecting(false);
    }
}

void Gpu::runProcess(const QString& program, const QStringList& args, std::function<void(const QByteArray&)> callback) {
    auto* proc = new QProcess(this);
    proc->setStandardErrorFile(QProcess::nullDevice());

    // Deliver the result exactly once, then tear the process down. A crash, a missing
    // binary or a failed run yields empty output so the caller can fall through
    // gracefully: only FailedToStart skips finished(), and a crash reports CrashExit there.
    const auto delivered = std::make_shared<bool>(false);
    const auto finish = [proc, delivered, callback = std::move(callback)](const QByteArray& out) {
        if (std::exchange(*delivered, true)) return;
        callback(out);
        proc->deleteLater();
    };
    auto* deadline=new QTimer(proc);
    deadline->setSingleShot(true);
    QObject::connect(deadline,&QTimer::timeout,this,[proc,finish] {proc->kill();finish(QByteArray());});
    deadline->start(2000);

    QObject::connect(proc, &QProcess::finished, this, [finish, proc](int code, QProcess::ExitStatus status) {
        const bool ok = status == QProcess::NormalExit && code == 0; // Fail on crashes and non-zero exit codes
        finish(ok ? proc->readAllStandardOutput() : QByteArray());
    });
    QObject::connect(proc, &QProcess::errorOccurred, this, [finish](QProcess::ProcessError err) {
        if (err == QProcess::FailedToStart) {
            finish(QByteArray());
        }
    });

    proc->start(program, args);
}

void Gpu::onStopped() {
    ++m_usageGeneration;m_metrics.reset();m_nvidiaQuerying=false;
}
void Gpu::startGpuUsage() {
    if (m_nvidiaQuerying) return;
    m_nvidiaQuerying=true;
    const int generation=m_usageGeneration;
    m_metrics.request([this,generation](double nativeUsage,double nativeTemperature,double,bool available) {
        if (generation!=m_usageGeneration) return;
        if (available && nativeUsage>=0) {
            const auto next=nativeUsage/100.0;
            if(std::abs(next-m_percentage)>.0001){m_percentage=next;emit percentageChanged();}
            if(nativeTemperature>0 && std::abs(nativeTemperature-m_temperature)>.05){m_temperature=nativeTemperature;emit temperatureChanged();}
            m_nvidiaQuerying=false;return;
        }
        if (m_type!=GpuType::Nvidia) {m_nvidiaQuerying=false;resetUsage();return;}
        if (TickingService::gaming()) {m_nvidiaQuerying=false;return;}
        // Unsupported NVIDIA drivers retain the bounded CLI fallback at <= 0.2 Hz.
        if (m_fallbackSample.isValid() && m_fallbackSample.elapsed()<5000) {m_nvidiaQuerying=false;return;}
        m_fallbackSample.start();
        runProcess(u"nvidia-smi"_s,
            {u"--query-gpu=utilization.gpu,temperature.gpu"_s,u"--format=csv,noheader,nounits"_s},
            [this,generation](const QByteArray& out) {
                if(generation!=m_usageGeneration)return;
                m_nvidiaQuerying=false;
                const auto parts=out.trimmed().split(',');if(parts.size()<2)return;
                bool usageOk=false,tempOk=false;
                const auto usage=parts[0].trimmed().toDouble(&usageOk)/100.0;
                const auto temp=parts[1].trimmed().toDouble(&tempOk);
                if(usageOk && usage>=0 && usage<=1 && std::abs(usage-m_percentage)>.0001){m_percentage=usage;emit percentageChanged();}
                if(tempOk && temp>0 && temp<150 && std::abs(temp-m_temperature)>.05){m_temperature=temp;emit temperatureChanged();}
            });
    },false,m_type==GpuType::Nvidia?QByteArrayLiteral("nvidia"):QByteArrayLiteral("generic"));
}


void Gpu::resetUsage() {
    if (std::abs(m_percentage) > 0.0001) {
        m_percentage = 0.0;
        emit percentageChanged();
    }
    if (std::abs(m_temperature) > 0.05) {
        m_temperature = 0.0;
        emit temperatureChanged();
    }
}

} // namespace hyprstack::services
