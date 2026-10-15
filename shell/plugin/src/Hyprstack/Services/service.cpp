#include "service.hpp"

namespace hyprstack::services {

Service::Service(QObject* parent)
    : QObject(parent) {}

void Service::ref(QObject* sender) {
    if (!sender || m_refs.contains(sender))
        return;
    if (m_refs.isEmpty()) {
        start();
    }

    QObject::connect(sender, &QObject::destroyed, this, &Service::unref);
    m_refs << sender;
}

void Service::unref(QObject* sender) {
    if (m_refs.remove(sender)) {
        QObject::disconnect(sender, &QObject::destroyed, this, &Service::unref);
        if (m_refs.isEmpty())
            stop();
    }
}

} // namespace hyprstack::services
