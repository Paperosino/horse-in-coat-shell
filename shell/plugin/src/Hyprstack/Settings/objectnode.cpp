#include "objectnode.hpp"

#include <qjsonobject.h>
#include <functional>

#include "util/i18n.hpp"
#include "codecs.hpp"

namespace hyprstack::settings {

using Qt::StringLiterals::operator""_s;

ObjectNode::ObjectNode(ObjectNode* fallback, QObject* parent, bool globalOnly)
    : Node(fallback, parent, globalOnly) {}

QVariantList ObjectNode::settingsRows() const {
  QVariantList rows;
  std::function<void(const Node *, QString)> visit = [&](const Node *node,
                                                         QString prefix) {
    for (const auto &desc : node->schema().descriptors()) {
      const auto path =
          prefix.isEmpty() ? desc.key : prefix + u"."_s + desc.key;
      auto val = node->value(desc.key);
      if (desc.isNode) {
        const auto *child = val.value<Node *>();
        if (qobject_cast<const ObjectNode *>(child))
          visit(child, path);
        else if (child)
          rows << QVariantMap{{u"path"_s, path},
                              {u"type"_s, u"json"_s},
                              {u"value"_s, child->toJson(false).toVariant()},
                              {u"overridden"_s, node->isOverride(desc.key)}};
      } else
        rows << QVariantMap{
            {u"path"_s, path},
            {u"type"_s, desc.typeString()},
            {u"value"_s, val},
            {u"default"_s, node->fallbackNode()
                               ? node->fallbackNode()->value(desc.key)
                               : desc.defaultValue()},
            {u"overridden"_s, node->isOverride(desc.key)}};
    }
  };
  visit(this, {});
  return rows;
}
bool ObjectNode::resetSetting(const QString &path) {
  auto parts = path.split(u'.');
  ObjectNode *node = this;
  for (qsizetype i = 0; i + 1 < parts.size(); ++i) {
    const auto *d = node->schema().get(parts[i]);
    if (!d || !d->isNode)
      return false;
    node = qobject_cast<ObjectNode *>(node->value(parts[i]).value<Node *>());
    if (!node)
      return false;
  }
  if (parts.isEmpty() || !node->schema().get(parts.last()))
    return false;
  node->resetOption(parts.last());
  return true;
}
bool ObjectNode::editSetting(const QString &path, const QVariant &value) {
  auto parts = path.split(u'.');
  ObjectNode *node = this;
  for (qsizetype i = 0; i + 1 < parts.size(); ++i) {
    const auto *d = node->schema().get(parts[i]);
    if (!d || !d->isNode)
      return false;
    node = qobject_cast<ObjectNode *>(node->value(parts[i]).value<Node *>());
    if (!node)
      return false;
  }
  if (parts.isEmpty())
    return false;
  const auto *d = node->schema().get(parts.last());
  if (!d || d->isNode)
    return false;
  auto converted = value;
  if (d->type.id() != QMetaType::QVariant && !converted.convert(d->type))
    return false;
  const WriteScope scope(node, WriteOrigin::Qml);
  return node->setValue(parts.last(), converted);
}

void ObjectNode::resetOption(const QString& key) {
    const auto* desc = schema().get(key);

    if (!desc) {
        qCWarning(lcSettings) << "Attempted to reset unknown option" << pathFor(key);
        return;
    }

    // Warn and ignore if this is a global node property and we are an overlay
    if (desc->isNode && (m_globalOnly || desc->globalOnly()) && fallbackNode()) {
        qCWarning(lcSettings,
            "Attempted to reset global node %s, ignoring. "
            "This should not be used, reset global nodes from the global layer instead.",
            qUtf8Printable(pathFor(key)));
        return;
    }

    const WriteScope scope(this, WriteOrigin::QmlReset);
    if (desc->isNode)
        value(key).value<Node*>()->resetToDefaults();
    else
        setValue(key, fallbackNode() ? fallbackNode()->value(key) : desc->defaultValue());
}

Descriptor ObjectNode::descriptorFor(const QString& key) const {
    const auto* desc = schema().get(key);
    if (!desc) {
        qCWarning(lcSettings) << "Attempted to get descriptor for unknown option" << pathFor(key);
        return {};
    }

    return *desc;
}

QJsonValue ObjectNode::toJson(bool sparse) const {
    QJsonObject json;

    for (const auto& desc : schema().descriptors()) {
        const auto val = value(desc.key);

        if (const auto* node = val.value<Node*>()) {
            if (!sparse || node->hasContent())
                json.insert(desc.key, node->toJson(sparse));
            continue;
        }

        if (sparse && !isOverride(desc.key))
            continue;

        if (!desc.codec) { // This should not happen
            qCCritical(lcSettings, "No codec found for type %s, not serialising %s", desc.type.name(),
                qUtf8Printable(pathFor(desc.key)));
            continue;
        }

        json.insert(desc.key, desc.codec->encode(val));
    }

    if (m_quarantine)
        return m_quarantine->apply(json);

    return json;
}

bool ObjectNode::syncJson(const QJsonValue& json, QList<Diagnostic>& diagnostics) {
    m_quarantine.reset(); // Clear out old quarantine

    if (!json.isObject()) {
        const auto d = Diagnostic::mismatch(ExpectedType::Object, json, path());
        qCWarning(lcSettings, "Error decoding option %s: %s", qUtf8Printable(d.option), qUtf8Printable(d.message));
        diagnostics << d;
        return false;
    }

    // Refuse syncs to global only nodes on overlays
    if (rejectGlobalSync(diagnostics))
        return false;

    const auto obj = json.toObject();

    qCDebug(lcSettings) << "Loading JSON into" << metaObject()->className() << "with" << obj.size()
                        << "keys:" << obj.keys();

    const auto visited = loadFromJson(obj, diagnostics);
    resetUnvisited(visited);

    return true;
}

void ObjectNode::quarantineKey(const QString& key, const QJsonValue& value) {
    if (!m_quarantine)
        m_quarantine = std::make_unique<ObjectQuarantine>();
    m_quarantine->insert(key, value);
}

QSet<QString> ObjectNode::loadFromJson(const QJsonObject& json, QList<Diagnostic>& diagnostics) {
    const WriteScope scope(this, WriteOrigin::File);

    QSet<QString> visited;
    visited.reserve(json.size());

    // Convenience macro for quarantine then skip
#define SKIP                                                                                                           \
    quarantineKey(key, v);                                                                                             \
    continue

    for (const auto [k, v] : json.asKeyValueRange()) {
        const auto key = k.toString();
        const auto* desc = schema().get(key);

        if (!desc) {
            const auto path = pathFor(key);
            qCWarning(lcSettings) << "Unknown option" << path;
            diagnostics << Diagnostic{
                .type = DiagnosticType::UnknownOption,
                .option = path,
                // TRANSLATORS: %1 = a config key name
                .message = util::i18n::mark(u"Unknown option %1"_s, { key }),
            };
            SKIP;
        }

        // Recurse into child nodes
        if (desc->isNode) {
            qCDebug(lcSettings) << "  Recursing into" << key;
            auto* const node = value(key).value<Node*>();
            if (node->syncJson(v, diagnostics))
                visited << key;
            else
                quarantineKey(key, v); // Quarantine entire node cause sync failed
            continue;
        }

        if ((m_globalOnly || desc->globalOnly()) && fallbackNode()) {
            warnGlobalSync(diagnostics, pathFor(key));
            SKIP;
        }

        if (!desc->codec) { // This should not happen
            qCCritical(lcSettings, "No codec found for type %s, not loading %s", desc->type.name(),
                qUtf8Printable(pathFor(key)));
            SKIP;
        }

        auto val = desc->codec->decode(v);
        if (val.error) {
            auto path = pathFor(key);
            for (const auto index : std::as_const(val.indexPath))
                path = elementPath(path, QString::number(index));
            qCWarning(lcSettings, "Error decoding option %s: %s", qUtf8Printable(path),
                qUtf8Printable(util::i18n::unmark(val.error->message)));
            val.error->option = path;
            diagnostics << *val.error;
            SKIP;
        }

        visited << key;
        setValue(key, val.value);
    }

#undef SKIP

    return visited;
}

void ObjectNode::resetUnvisited(const QSet<QString>& visited) {
    const WriteScope scope(this, WriteOrigin::FileReset);

    for (const auto& desc : schema().descriptors()) {
        if (visited.contains(desc.key))
            continue;

        // Reset nodes recursively
        if (desc.isNode) {
            value(desc.key).value<Node*>()->resetToDefaults();
            continue;
        }

        // Skip global options on overlays
        if ((m_globalOnly || desc.globalOnly()) && fallbackNode())
            continue;

        setValue(desc.key, fallbackNode() ? fallbackNode()->value(desc.key) : desc.defaultValue());
    }
}

} // namespace hyprstack::settings
