import QtQuick
import Hyprstack.Config

ColorAnimation {
    duration: GlobalConfig.appearance.reducedMotion ? 0 : Tokens.anim.durations.expressiveSlowEffects
    easing: Tokens.anim.expressiveSlowEffects
}
