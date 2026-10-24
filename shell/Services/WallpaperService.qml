pragma Singleton
import Quickshell
import qs.services
Singleton {
    readonly property string currentWallpaper: Wallpapers.actualCurrent
    function getWallpaper(screen = null): string { return Wallpapers.actualCurrent; }
    function setWallpaper(path: string, screen = null): void {
        if (screen?.name) LiveWallpapers.save(screen.name, Object.assign({}, LiveWallpapers.forScreen(screen.name), {kind: "static"}));
        Wallpapers.setWallpaper(path);
    }
}
