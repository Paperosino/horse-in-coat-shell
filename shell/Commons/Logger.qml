pragma Singleton
import Quickshell
Singleton {
    function d(scope: string, text: string): void { console.debug(scope, text); }
    function i(scope: string, text: string): void { console.info(scope, text); }
    function w(scope: string, text: string): void { console.warn(scope, text); }
    function e(scope: string, text: string): void { console.error(scope, text); }
    function debug(scope: string, text: string): void { console.debug(scope, text); }
    function info(scope: string, text: string): void { console.info(scope, text); }
    function warn(scope: string, text: string): void { console.warn(scope, text); }
    function error(scope: string, text: string): void { console.error(scope, text); }
}
