import QtQuick
import Quickshell
import Hyprstack.Images

// One shared, event-driven observer supplies an empty URL when no avatar exists.
Image {
    asynchronous: true
    fillMode: Image.PreserveAspectCrop
    source: width > 0 && height > 0 ? IUtils.profilePicture : ""
    sourceSize: {
        const dpr = (QsWindow.window as QsWindow)?.devicePixelRatio ?? 1;
        return Qt.size(width * dpr, height * dpr);
    }
}
