pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
ColumnLayout {
    id:root
    property bool ipv6:false
    property var settings:({})
    signal edited(string key,var value)
    Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
    SectionHeader { text:root.ipv6?"IPv6 / DNS":"IPv4 / DNS" }
    GenericSettingRow { spec:({label:"Address configuration",type:"choice",choices:["auto","manual","disabled","link-local"]});value:root.settings.method??"auto";onEdited:v=>root.edited("method",v) }
    VpnTextArea { label:"IP addresses";hint:"One address/prefix per line";value:root.settings.addresses??"";onEdited:v=>root.edited("addresses",v) }
    TextFieldRow {label:Tr.tr("Gateway");value:root.settings.gateway??"";onValueEdited:v=>root.edited("gateway",v)}
    TextFieldRow { label:Tr.tr("DNS servers");subtext:Tr.tr("Separate servers with commas");value:root.settings.dns??"";onValueEdited:v=>root.edited("dns",v) }
    TextFieldRow { label:Tr.tr("Search and routing domains");subtext:Tr.tr("Use ~domain for split DNS, ~. for all domains");value:root.settings.domains??"";onValueEdited:v=>root.edited("domains",v) }
    ToggleRow { text:Tr.tr("Ignore DNS provided by VPN");checked:!!root.settings.ignoreAutoDns;onToggled:v=>root.edited("ignoreAutoDns",v) }
    GenericSettingRow { spec:({label:"DNS priority",type:"number",min:-2147483648,max:2147483647});value:root.settings.priority??0;onEdited:v=>root.edited("priority",v) }
    InfoRow { first:true;last:true;label:Tr.tr("Exclusive VPN DNS");value:Tr.tr("A negative DNS priority excludes DNS from connections with higher priorities while this VPN is active.") }
    ToggleRow { text:Tr.tr("Use only for resources on this network");checked:!!root.settings.neverDefault;onToggled:v=>root.edited("neverDefault",v) }
    ToggleRow { text:Tr.tr("Ignore routes provided by VPN");checked:!!root.settings.ignoreAutoRoutes;onToggled:v=>root.edited("ignoreAutoRoutes",v) }
    GenericSettingRow { spec:({label:"Route metric",type:"number",min:-1,max:4294967295});value:root.settings.metric??-1;onEdited:v=>root.edited("metric",v) }
    VpnTextArea { label:"Static routes";hint:"One route per line: network/prefix next-hop metric. Use - for no next-hop and -1 for automatic metric.";value:root.settings.routes??"";onEdited:v=>root.edited("routes",v) }
    VpnTextArea { label:"Policy routing rules";hint:"One rule per line, for example: priority 100 from 10.0.0.0/24 table 100";value:root.settings.rules??"";onEdited:v=>root.edited("rules",v) }
}
