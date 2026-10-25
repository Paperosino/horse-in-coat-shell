pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services

Singleton {
    id: root
    readonly property bool visualiserAvailable: cava.available

    property string safetyLastSink: ""
    property string safetyTarget: ""
    function protectOutputSwitch(): void {
        const id=sink?.name??"";
        if(!id||id===safetyLastSink)return;
        const previous=safetyLastSink;safetyLastSink=id;
        if(previous&&GlobalConfig.utilities.comfort.safeAudioSwitch){safetyTarget=id;outputSafety.restart();}
    }
    Timer {
        id:outputSafety;interval:250
        onTriggered:{
            if(!GlobalConfig.utilities.comfort.safeAudioSwitch||root.sink?.name!==root.safetyTarget||!root.sink?.ready||!root.sink?.audio)return;
            const limit=Math.max(5,Math.min(100,GlobalConfig.utilities.comfort.switchVolumePercent))/100;
            if(root.sink.audio.volume>limit)root.sink.audio.volume=limit;
        }
    }
    Connections {target:root.sink;function onReadyChanged():void{if(root.sink?.ready&&root.sink.name===root.safetyTarget)outputSafety.restart();}}
    property string previousSinkName: ""
    property string previousSourceName: ""

    property list<PwNode> sinks: []
    property list<PwNode> sources: []
    property list<PwNode> streams: []

    readonly property PwNode sink: Pipewire.defaultAudioSink
    readonly property PwNode source: Pipewire.defaultAudioSource

    readonly property bool muted: !!sink?.audio?.muted
    readonly property real volume: sink?.audio?.volume ?? 0

    readonly property bool sourceMuted: !!source?.audio?.muted
    readonly property real sourceVolume: source?.audio?.volume ?? 0

    readonly property alias cava: cava
    readonly property alias beatTracker: beatTracker

    readonly property bool privacyMuted: GlobalConfig.general.privacy.microphoneMuted
    property var previousMutes: GlobalConfig.general.privacy.microphonePreviousMutes
    readonly property var microphoneStreams: streams.filter(n => n.type === PwNodeType.AudioInStream)
    readonly property real balance: {
        const a=sink?.audio;if(!a)return 0;
        const left=a.channels.indexOf(PwAudioChannel.FrontLeft),right=a.channels.indexOf(PwAudioChannel.FrontRight);
        if(left<0||right<0)return 0;
        const l=a.volumes[left],r=a.volumes[right],m=Math.max(l,r);
        return m>0?(r-l)/m:0;
    }
    readonly property bool stereoOutput: sink?.audio?.channels.includes(PwAudioChannel.FrontLeft) && sink?.audio?.channels.includes(PwAudioChannel.FrontRight) || false
    function setBalance(value:real):void {
        const a=sink?.audio;if(!a)return;
        const channels=a.channels,volumes=Array.from(a.volumes),l=channels.indexOf(PwAudioChannel.FrontLeft),r=channels.indexOf(PwAudioChannel.FrontRight);
        if(l<0||r<0)return;
        const peak=Math.max(volumes[l],volumes[r]);value=Math.max(-1,Math.min(1,value));
        volumes[l]=peak*(value>0?1-value:1);volumes[r]=peak*(value<0?1+value:1);a.volumes=volumes;
    }
    function enforceMicrophonePrivacy():void {
        if(!privacyMuted)return;
        const old=Object.assign({},previousMutes);
        for(const node of sources)if(node.ready&&node.audio){if(old[node.name]===undefined)old[node.name]=node.audio.muted;node.audio.muted=true;}
        GlobalConfig.general.privacy.microphonePreviousMutes=old;
    }
    function setMicrophonePrivacy(blocked:bool):void {
        if(blocked===privacyMuted)return;
        GlobalConfig.general.privacy.microphoneMuted=blocked;
    }
    onPrivacyMutedChanged: {
        if(privacyMuted)enforceMicrophonePrivacy();
        else{for(const node of sources)if(node.ready&&node.audio&&previousMutes[node.name]!==undefined)node.audio.muted=previousMutes[node.name];GlobalConfig.general.privacy.microphonePreviousMutes=({});}
    }
    Instantiator {
        model: root.sources
        delegate: QtObject {
            required property var modelData
            property Connections muteWatch: Connections {target:modelData.audio;function onMutedChanged():void{if(root.privacyMuted&&modelData.ready&&!modelData.audio.muted)root.enforceMicrophonePrivacy();}}
            property Connections readyWatch: Connections {target:modelData;function onReadyChanged():void{root.enforceMicrophonePrivacy();}}
        }
    }
    onSourcesChanged: enforceMicrophonePrivacy()
    Connections {target:root.source?.audio??null;function onMutedChanged():void{if(root.privacyMuted&&!root.source.audio.muted)root.source.audio.muted=true;}}
    function setVolume(newVolume: real): void {
        if (sink?.ready && sink?.audio) {
            sink.audio.muted = false;
            sink.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function incrementVolume(amount: real): void {
        setVolume(volume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementVolume(amount: real): void {
        setVolume(volume - (amount || GlobalConfig.services.audioIncrement));
    }

    function setSourceVolume(newVolume: real): void {
        if (privacyMuted) return;
        if (source?.ready && source?.audio) {
            source.audio.muted = false;
            source.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function incrementSourceVolume(amount: real): void {
        setSourceVolume(sourceVolume + (amount || GlobalConfig.services.audioIncrement));
    }

    function decrementSourceVolume(amount: real): void {
        setSourceVolume(sourceVolume - (amount || GlobalConfig.services.audioIncrement));
    }

    function setAudioSink(newSink: PwNode): void {
        Pipewire.preferredDefaultAudioSink = newSink;
    }

    function setAudioSource(newSource: PwNode): void {
        Pipewire.preferredDefaultAudioSource = newSource;
    }

    function cycleNextAudioOutput(): void {
        if (sinks.length === 0)
            return;

        const currentIndex = sinks.findIndex(s => s === sink);
        const nextIndex = (currentIndex + 1) % sinks.length;
        setAudioSink(sinks[nextIndex]);
    }

    function setStreamVolume(stream: PwNode, newVolume: real): void {
        if (stream?.ready && stream?.audio) {
            stream.audio.muted = false;
            stream.audio.volume = Math.max(0, Math.min(GlobalConfig.services.maxVolume, newVolume));
        }
    }

    function setStreamMuted(stream: PwNode, muted: bool): void {
        if(privacyMuted && sources.includes(stream) && !muted)return;
        if (stream?.ready && stream?.audio) {
            stream.audio.muted = muted;
        }
    }

    function getStreamVolume(stream: PwNode): real {
        return stream?.audio?.volume ?? 0;
    }

    function getStreamMuted(stream: PwNode): bool {
        return !!stream?.audio?.muted;
    }

    function getStreamName(stream: PwNode): string {
        if (!stream)
            return Tr.trCtx("Unknown", "unknown audio stream");
        // Try application name first, then description, then name
        return stream.properties["application.name"] || stream.description || stream.name || Tr.trCtx("Unknown application", "unknown application audio stream");
    }

    function refreshNodes(): void {
        const newSinks = [];
        const newSources = [];
        const newStreams = [];

        for (const node of Pipewire.nodes.values) {
            if (!node.isStream) {
                if (node.audio && (node.type & PwNodeType.Sink))
                    newSinks.push(node);
                if (node.audio && (node.type & PwNodeType.Source))
                    newSources.push(node);
            } else if (node.audio) {
                newStreams.push(node);
            }
        }

        root.sinks = newSinks;
        root.sources = newSources;
        root.streams = newStreams;
    }

    onSinkChanged: {
        protectOutputSwitch();
        if (!sink?.ready)
            return;

        const newSinkName = sink.description || sink.name || Tr.trCtx("Unknown device", "unknown audio device");

        if (previousSinkName && previousSinkName !== newSinkName && GlobalConfig.utilities.toasts.audioOutputChanged)
            Toaster.toast(Tr.tr("Audio output changed"), Tr.tr("Now using: %1").arg(newSinkName), "volume_up");

        previousSinkName = newSinkName;
    }

    onSourceChanged: {
        if (!source?.ready)
            return;

        const newSourceName = source.description || source.name || Tr.trCtx("Unknown device", "unknown audio device");

        if (previousSourceName && previousSourceName !== newSourceName && GlobalConfig.utilities.toasts.audioInputChanged)
            Toaster.toast(Tr.tr("Audio input changed"), Tr.tr("Now using: %1").arg(newSourceName), "mic");

        previousSourceName = newSourceName;
    }

    // Populate immediately: Pipewire.nodes may already be filled by the time this
    // lazily-loaded singleton is created, so onValuesChanged would never fire.
    Component.onCompleted: {
        refreshNodes();
        previousSinkName = sink?.description || sink?.name || Tr.trCtx("Unknown device", "unknown audio device");
        previousSourceName = source?.description || source?.name || Tr.trCtx("Unknown device", "unknown audio device");
    }

    Connections {
        function onValuesChanged(): void {
            root.refreshNodes();
        }

        target: Pipewire.nodes
    }

    // Always track the current defaults so volume/mute bind even if the lists
    // momentarily lag behind the default node.
    PwObjectTracker {
        objects: [root.sink, root.source, ...root.sinks, ...root.sources, ...root.streams].filter(n => n)
    }

    CavaProvider {
        id: cava

        bars: GlobalConfig.services.visualiserBars
    }

    BeatTracker {
        id: beatTracker
    }

    IpcHandler {
        function cycleOutput(): void {
            root.cycleNextAudioOutput();
        }

        target: "audio"
    }
}
