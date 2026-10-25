#pragma once

#include <qstring.h>
#include <qvariantlist.h>

#include "settings/objectnode.hpp"
#include "common.hpp"

namespace hyprstack::config {

using Qt::StringLiterals::operator""_s;

class UtilitiesToasts : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesToasts, settings::ObjectNode)

    CONFIG_PROPERTY(QString, fullscreen, u"off"_s)
    CONFIG_PROPERTY(bool, configLoaded, true)
    CONFIG_PROPERTY(bool, chargingChanged, true)
    CONFIG_PROPERTY(bool, gameModeChanged, true)
    CONFIG_PROPERTY(bool, dndChanged, true)
    CONFIG_PROPERTY(bool, audioOutputChanged, true)
    CONFIG_PROPERTY(bool, audioInputChanged, true)
    CONFIG_PROPERTY(bool, capsLockChanged, true)
    CONFIG_PROPERTY(bool, numLockChanged, true)
    CONFIG_PROPERTY(bool, kbLayoutChanged, true)
    CONFIG_PROPERTY(bool, kbLimit, true)
    CONFIG_PROPERTY(bool, vpnChanged, true)
    CONFIG_PROPERTY(bool, nowPlaying, false)
};

class UtilitiesVpnProvider : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesVpnProvider, settings::ObjectNode)

    CONFIG_PROPERTY(QString, id, {})
    CONFIG_PROPERTY(QString, name, {})
    CONFIG_PROPERTY(QString, displayName, {})
    CONFIG_PROPERTY(QString, interface, {})
    CONFIG_PROPERTY(QStringList, connectCmd, {})
    CONFIG_PROPERTY(QStringList, disconnectCmd, {})
};
CONFIG_LIST_TYPE(UtilitiesVpnProvider, UtilitiesVpnProviderList)

class UtilitiesVpn : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesVpn, settings::ObjectNode)

    CONFIG_PROPERTY(bool, enabled, false)
    CONFIG_LIST(UtilitiesVpnProviderList, provider, {})
    CONFIG_PROPERTY(QString, selectedProvider, {})
};

class UtilitiesCards : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesCards, settings::ObjectNode)

    CONFIG_PROPERTY(bool, keepAwake, true)
    CONFIG_PROPERTY(bool, recorder, true)
    CONFIG_PROPERTY(bool, quickToggles, true)
};

class UtilitiesOperations : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesOperations, settings::ObjectNode)
    CONFIG_PROPERTY(bool, autoShow, true)
    CONFIG_PROPERTY(bool, retainErrors, true)
    CONFIG_PROPERTY(int, completedSeconds, 12)
    CONFIG_PROPERTY(bool, showProgress, true)
    CONFIG_PROPERTY(bool, watchUnresponsive, true)
    CONFIG_PROPERTY(int, unresponsiveMissedPings, 5)
};

class UtilitiesPresentation : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesPresentation, settings::ObjectNode)
    CONFIG_PROPERTY(int, durationMinutes, 60)
    CONFIG_PROPERTY(bool, hideNotifications, true)
    CONFIG_PROPERTY(bool, hidePrivateContent, true)
};

class UtilitiesConfig : public settings::ObjectNode {
    CONFIG_NODE(UtilitiesConfig, settings::ObjectNode)

    CONFIG_PROPERTY(bool, enabled, true)
    CONFIG_PROPERTY(int, maxToasts, 4)
    CONFIG_SUBOBJECT(UtilitiesCards, cards)
    CONFIG_GLOBAL_SUBOBJECT(UtilitiesToasts, toasts)
    CONFIG_GLOBAL_SUBOBJECT(UtilitiesVpn, vpn)
    CONFIG_GLOBAL_SUBOBJECT(UtilitiesOperations, operations)
    CONFIG_GLOBAL_SUBOBJECT(UtilitiesPresentation, presentation)
    CONFIG_LIST(EntryList, quickToggles,
        DEFAULT_ARG({
            LIST_ENTRY(wifi, true),
            LIST_ENTRY(bluetooth, true),
            LIST_ENTRY(mic, true),
            LIST_ENTRY(settings, true),
            LIST_ENTRY(gameMode, true),
            LIST_ENTRY(dnd, true),
            LIST_ENTRY(vpn, false),
            LIST_ENTRY(presentation, true),
            LIST_ENTRY(camera, true),
        }))
};

} // namespace hyprstack::config
