pragma ComponentBehavior: Bound
import QtQuick

// Seconds-based damped oscillator, integrated on rendered frames. Substeps keep
// the response stable across 60–240 Hz and after a delayed frame.
QtObject {
    id: root
    property real target: 0
    property real value: 0
    property real velocity: 0
    property real stiffness: 280
    property real damping: 0.8
    property bool enabled: true
    onEnabledChanged: if (!enabled) { value = target; velocity = 0; }
    onTargetChanged: if (!enabled) { value = target; velocity = 0; }
    property FrameAnimation driver: FrameAnimation {
        running: root.enabled && (Math.abs(root.target-root.value)>0.0005 || Math.abs(root.velocity)>0.005)
        onTriggered: {
            const dt = Math.min(frameTime, 0.032);
            const steps = Math.max(1, Math.ceil(dt*240));
            const h = dt/steps;
            const drag = 2*root.damping*Math.sqrt(root.stiffness);
            let v = root.velocity, x = root.value;
            for (let i=0; i<steps; ++i) {
                v += ((root.target-x)*root.stiffness-drag*v)*h;
                x += v*h;
            }
            if (Math.abs(root.target-x)<0.0005 && Math.abs(v)<0.005) { x=root.target; v=0; }
            root.velocity=v; root.value=x;
        }
    }
}
