.pragma library

// Follow plasma-nm's split between credentials and protocol/IP tuning, and its
// authentication-specific forms. This policy never removes hidden data.
function protocolId(type) { return String(type || "").split(".").pop(); }
function defaults(type) {
    switch (protocolId(type)) {
    case "openvpn": return {"connection-type":"tls"};
    case "l2tp": return {"user-auth-type":"password", "machine-auth-type":"psk", "ipsec-enabled":"yes"};
    case "openconnect": return {protocol:"anyconnect"};
    case "libreswan": return {ikev2:"no"};
    case "strongswan": return {method:"eap"};
    default: return {};
    }
}
function basicKeys(type) {
    return ({
        openvpn:["remote","connection-type","username","password","ca","cert","key","cert-pass","static-key","local-ip","remote-ip","ta-dir"],
        pptp:["gateway","user","password","domain"],
        l2tp:["gateway","user-auth-type","user","password","domain","user-ca","user-cert","user-key","user-certpass","ipsec-enabled","machine-auth-type","ipsec-psk","machine-ca","machine-cert","machine-key","machine-certpass"],
        openconnect:["gateway","protocol","usergroup"],
        vpnc:["IPSec gateway","IPSec ID","IPSec secret","Xauth username","Xauth password"],
        strongswan:["address","method","user","password","certificate","usercert","userkey"],
        libreswan:["ikev2","right","leftid","rightid","leftxauthusername","xauthpassword","pskvalue","leftcert"],
        sstp:["gateway","user","password","domain","ca-cert"],
        fortisslvpn:["gateway","user","password","realm"],
        ssh:["remote","remote-username","key-file","password","key-passphrase","local-ip","remote-ip","netmask"]
    })[protocolId(type)] || [];
}
function fieldVisible(type, field, data, advanced) {
    const id = protocolId(type), key = field.key;
    const basic = basicKeys(type).includes(key) && !(id === "openvpn" && key === "ta-dir" && data["connection-type"] !== "static-key");
    if (basic === advanced) return false;
    if (id === "openvpn") {
        const mode = data["connection-type"] || "tls";
        if (["username","password"].includes(key)) return ["password","password-tls"].includes(mode);
        if (["cert","key","cert-pass"].includes(key)) return ["tls","password-tls"].includes(mode);
        if (["static-key","local-ip","remote-ip"].includes(key)) return mode === "static-key";
        if (key === "ca") return mode !== "static-key";
    }
    if (id === "strongswan") {
        const method = data.method || "eap";
        if (key === "user") return ["eap","smartcard"].includes(method);
        if (key === "password") return ["eap","psk"].includes(method);
        if (key === "usercert") return ["key","agent"].includes(method);
        if (key === "userkey") return method === "key";
    }
    if (id === "l2tp") {
        const tls = data["user-auth-type"] === "tls";
        if (["user","password","domain"].includes(key)) return !tls;
        if (key.startsWith("user-") && key !== "user-auth-type") return tls;
        if (field.section === "IPsec" && key !== "ipsec-enabled") {
            if (data["ipsec-enabled"] !== "yes") return false;
            const machineTls = data["machine-auth-type"] === "tls";
            if (key === "ipsec-psk") return !machineTls;
            if (key.startsWith("machine-") && key !== "machine-auth-type") return machineTls;
        }
    }
    return true;
}

// Keep only explicitly shared, non-secret values when changing protocol.
function changeProtocol(form, type) {
    const gateways = {openvpn:"remote",pptp:"gateway",l2tp:"gateway",openconnect:"gateway",vpnc:"IPSec gateway",strongswan:"address",libreswan:"right",sstp:"gateway",fortisslvpn:"gateway",ssh:"remote"};
    const users = {openvpn:"username",pptp:"user",l2tp:"user",vpnc:"Xauth username",strongswan:"user",libreswan:"leftxauthusername",sstp:"user",fortisslvpn:"user",ssh:"remote-username"};
    const oldId=protocolId(form.type), newId=protocolId(type);
    const data=defaults(type), oldData=form.data||{};
    if(gateways[newId] && oldData[gateways[oldId]])data[gateways[newId]]=oldData[gateways[oldId]];
    if(users[newId] && oldData[users[oldId]])data[users[newId]]=oldData[users[oldId]];
    const result=Object.assign({},form,{type:type,data:data,secrets:{},clearSecrets:[],wireguard:{peerRoutes:true,peers:[]},interface:""});
    if(type==="wireguard"){
        result.ip4=Object.assign({},form.ip4||{},{method:"manual"});
        result.ip6=Object.assign({},form.ip6||{},{method:"disabled"});
    }else if(oldId==="wireguard"){
        result.ip4=Object.assign({},form.ip4||{},{method:"auto",addresses:""});
        result.ip6=Object.assign({},form.ip6||{},{method:"auto",addresses:""});
    }
    return result;
}
