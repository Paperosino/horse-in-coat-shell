pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import qs.utils
import "WeatherData.js" as WeatherData

Singleton {
    id: root

    property string city
    property string loc
    property var cc
    property list<var> forecast
    property list<var> hourlyForecast

    property bool ipApiRequestPending: false
    property double ipApiBlockedUntil: 0
    property bool citiesLoaded: false
    property string pendingCoords
    property string error
    property bool weatherRequestPending: false
    property bool cityRequestPending: false
    property int locationGeneration: 0
    readonly property bool loading: ipApiRequestPending || weatherRequestPending || cityRequestPending
    readonly property string provider: GlobalConfig.services.weatherProvider === "wttr.in" ? "wttr.in" : "open-meteo"
    readonly property string providerName: provider === "wttr.in" ? "wttr.in" : "Open-Meteo"

    readonly property string icon: cc ? Icons.getWeatherIcon(cc.weatherCode) : "cloud_alert"
    readonly property string description: cc ? getWeatherCondition(cc.weatherCode)
        : loading ? Tr.tr("Loading weather…") : error || Tr.tr("No weather")
    readonly property string temp: formatTemp(cc?.tempC)
    readonly property string feelsLike: formatTemp(cc?.feelsLikeC)
    readonly property int humidity: cc?.humidity ?? 0
    readonly property real windSpeed: cc?.windSpeed ?? 0
    readonly property string sunrise: cc?.sunrise ? Qt.formatDateTime(new Date(cc.sunrise), Units.twelveHourClock ? "h:mm A" : "h:mm") : "--:--"
    readonly property string sunset: cc?.sunset ? Qt.formatDateTime(new Date(cc.sunset), Units.twelveHourClock ? "h:mm A" : "h:mm") : "--:--"

    readonly property var cachedCities: new Map()

    Component.onCompleted: reload()

    function formatTemp(temp: var, compact = false): string {
        const unit = GlobalConfig.services.weatherUnits;
        const value = temp !== undefined && temp !== null && Number.isFinite(temp) ? Math.round(Units.toTemperature(temp, unit)) : "--";
        return Units.formatTemp(value, unit, compact);
    }

    IpcHandler {
        target: "weather"
        function refresh(): void { root.reload(); }
        function status(): string {
            return JSON.stringify({enabled:GlobalConfig.services.weatherEnabled,loading:root.loading,
                city:root.city,coordinates:root.loc,temperature:root.cc?.tempC ?? null,
                provider:root.provider,locationMode:GlobalConfig.services.weatherLocation.trim() ? "city" : "ip",
                error:root.error,forecastDays:root.forecast.length});
        }
    }

    function reload(): void {
        if (!GlobalConfig.services.weatherEnabled)
            return;
        const configLocation = GlobalConfig.services.weatherLocation.trim();

        if (configLocation) {
            if (configLocation.indexOf(",") !== -1 && !isNaN(parseFloat(configLocation.split(",")[0]))) {
                const parts = configLocation.split(",").map(s => s.trim());
                const [lat, lon] = parts.map(Number);
                if (parts.length !== 2 || parts.some(s => !s) || !Number.isFinite(lat) || !Number.isFinite(lon)
                    || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
                    error = Tr.tr("Invalid weather coordinates");
                    return;
                }
                loc = `${lat},${lon}`;
                if (GlobalConfig.services.weatherLocationName)
                    city = GlobalConfig.services.weatherLocationName;
                else
                    fetchCityFromCoords(loc);
                fetchWeatherData();
            } else {
                fetchCoordsFromCity(configLocation);
            }
        } else if ((!loc || timer.elapsed() > 900) && !ipApiRequestPending && Date.now() >= ipApiBlockedUntil) {
            ipApiRequestPending = true;
            const generation = locationGeneration;

            Requests.get("http://ip-api.com/json?fields=status,message,city,lat,lon", (text, metadata) => {
                ipApiRequestPending = false;
                recordIpApiRateLimit(metadata);

                // Protect against stale responses overwriting the manually-set location,
                // in case the config was updated while this request was in-flight.
                if (obsoleteRequest(generation))
                    return;

                let response;
                try {
                    response = JSON.parse(text);
                } catch (error) {
                    console.warn(lc, `Unable to parse response from ip-api: ${error}`);
                    fetchFallbackLocation(generation);
                    return;
                }

                const lat = Number(response.lat);
                const lon = Number(response.lon);

                if (response.status !== "success" || !Number.isFinite(lat) || !Number.isFinite(lon)) {
                    console.warn(lc, `ip-api lookup failed: ${response.message ?? "invalid response"}`);
                    fetchFallbackLocation(generation);
                    return;
                }

                city = fixCityName(response.city ?? "");
                timer.restart();
                loc = `${lat},${lon}`;
                fetchWeatherData();
            }, (error, metadata) => {
                ipApiRequestPending = false;
                if (obsoleteRequest(generation))
                    return;

                if (!recordIpApiRateLimit(metadata))
                    console.warn(lc, `ip-api request failed: ${error}`);
                fetchFallbackLocation(generation);
            });
        } else if (loc) {
            fetchWeatherData();
        }
    }

    function obsoleteRequest(generation: int): bool {
        if (generation === locationGeneration && GlobalConfig.services.weatherEnabled)
            return false;
        if (GlobalConfig.services.weatherEnabled)
            Qt.callLater(() => root.reload());
        return true;
    }

    function fail(message: string): void {
        error = message;
        retryTimer.restart();
    }

    function fetchFallbackLocation(generation: int): void {
        ipApiRequestPending = true;
        Requests.get("https://ipwho.is/", text => {
            ipApiRequestPending = false;
            if (obsoleteRequest(generation))
                return;
            try {
                const response = JSON.parse(text);
                const lat = response.latitude, lon = response.longitude;
                if (!response.success || !Number.isFinite(lat) || !Number.isFinite(lon))
                    throw new Error("invalid location");
                city = fixCityName(response.city ?? "");
                loc = `${lat},${lon}`;
                timer.restart();
                fetchWeatherData();
            } catch (err) {
                root.fail(Tr.tr("Unable to determine weather location"));
            }
        }, err => {
            ipApiRequestPending = false;
            if (!obsoleteRequest(generation))
                root.fail(Tr.tr("Unable to determine weather location"));
        });
    }

    function recordIpApiRateLimit(metadata: var): bool {
        const remainingHeader = metadata?.headers?.["x-rl"];
        const exhausted = remainingHeader !== undefined && Number(remainingHeader) === 0;

        if (metadata?.statusCode !== 429 && !exhausted)
            return false;

        const ttlHeader = metadata?.headers?.["x-ttl"];
        const ttl = Number(ttlHeader);

        const delaySeconds = Number.isFinite(ttl) ? Math.max(1, Math.ceil(ttl) + 1) : 61;

        const delayMs = delaySeconds * 1000;
        ipApiBlockedUntil = Date.now() + delayMs;
        ipApiRetryTimer.interval = delayMs;
        ipApiRetryTimer.restart();

        return true;
    }

    function fixCityName(cityName: string): string {
        if (!cityName)
            return "";
        const mapping = {
            // Polish
            "Poznan": "Poznań",
            "Wroclaw": "Wrocław",
            "Krakow": "Kraków",
            "Gdansk": "Gdańsk",
            "Lodz": "Łódź",
            "Rzeszow": "Rzeszów",
            "Torun": "Toruń",
            "Bialystok": "Białystok",
            "Czestochowa": "Częstochowa",
            "Plock": "Płock",
            "Ruda Slaska": "Ruda Śląska",
            "Dabrowa Gornicza": "Dąbrowa Górnicza",
            "Elblag": "Elbląg",
            "Gorzow Wielkopolski": "Gorzów Wielkopolski",
            "Zielona Gora": "Zielona Góra",
            "Slupsk": "Słupsk",

            // German
            "Munchen": "München",
            "Koln": "Köln",
            "Dusseldorf": "Düsseldorf",
            "Nurnberg": "Nürnberg",

            // French & Spanish & Portuguese
            "Sao Paulo": "São Paulo",
            "Montreal": "Montréal",
            "Quebec": "Québec",
            "Bogota": "Bogotá",
            "Medellin": "Medellín",
            "Cordoba": "Córdoba",

            // Turkish
            "Istanbul": "İstanbul",
            "Izmir": "İzmir",

            // Scandinavian & others
            "Malmo": "Malmö",
            "Goteborg": "Göteborg",
            "Zurich": "Zürich",
            "Geneve": "Genève"
        };
        return mapping[cityName] || cityName;
    }

    function cacheCity(coords: string, cityName: string): void {
        cachedCities.set(coords, cityName);
        citiesSaveTimer.restart();
    }

    function citySearchLanguage(query: string): string {
        if (/ў/i.test(query))
            return "be";
        if (/[іїєґ]/i.test(query))
            return "uk";
        if (/[а-яё]/i.test(query))
            return "ru";
        const language = (Tr.language || Qt.locale().name).split("_")[0].toLowerCase();
        return /^[a-z]{2}$/.test(language) ? language : "en";
    }

    function searchCities(query: string, onSuccess: var, onError: var): void {
        const lang = citySearchLanguage(query);
        const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query.trim())}&count=6&language=${lang}&format=json`;
        Requests.get(url, text => {
            try {
                const json = JSON.parse(text);
                if (json.error)
                    throw new Error("city search failed");
                const results = (json.results ?? []).filter(result => typeof result.name === "string" && result.name.trim()
                    && Number.isFinite(result.latitude)
                    && Number.isFinite(result.longitude) && Math.abs(result.latitude) <= 90
                    && Math.abs(result.longitude) <= 180).map(result => ({
                        name:fixCityName(result.name),
                        label:[fixCityName(result.name), result.admin1, result.country]
                            .filter((value, index, values) => value && values.indexOf(value) === index).join(", "),
                        latitude:result.latitude, longitude:result.longitude
                    }));
                onSuccess(results);
            } catch (err) {
                onError(Tr.tr("Unable to search for cities"));
            }
        }, err => onError(Tr.tr("Unable to search for cities")));
    }

    function selectCity(result: var): void {
        if (!result?.name || !Number.isFinite(result.latitude) || !Number.isFinite(result.longitude)
            || Math.abs(result.latitude) > 90 || Math.abs(result.longitude) > 180)
            return;
        GlobalConfig.services.weatherLocationName = result.name;
        GlobalConfig.services.weatherLocationLabel = result.label || result.name;
        GlobalConfig.services.weatherLocation = `${result.latitude},${result.longitude}`;
    }

    function useAutomaticLocation(): void {
        GlobalConfig.services.weatherLocationName = "";
        GlobalConfig.services.weatherLocationLabel = "";
        GlobalConfig.services.weatherLocation = "";
    }

    function fetchCityFromCoords(coords: string): void {
        if (cachedCities.has(coords)) {
            city = cachedCities.get(coords);
            return;
        }

        // Defer until cache is loaded
        if (!citiesLoaded) {
            pendingCoords = coords;
            return;
        }

        const [lat, lon] = coords.split(",").map(s => s.trim());
        const lang = citySearchLanguage("");

        const nominatimUrl = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=geocodejson&accept-language=${lang}`;
        const nominatimHeaders = {
            "User-Agent": `hics-shell/${CUtils.version}`
        };

        Requests.get(nominatimUrl, text => {
            if (coords !== loc || !GlobalConfig.services.weatherEnabled)
                return;
            let geo;
            try {
                geo = JSON.parse(text).features?.[0]?.properties.geocoding;
            } catch (error) {
                console.warn(lc, `Unable to parse response from nominatim: ${error}`);
                city = Tr.trCtx("Unknown city", "weather location unavailable");
                return;
            }

            if (geo) {
                const geoCity = geo.type === "city" ? geo.name : geo.city;
                if (geoCity) {
                    city = fixCityName(geoCity);
                    cacheCity(coords, city);
                    return;
                }
            }

            console.warn(lc, "No locality in nominatim response");
            city = Tr.trCtx("Unknown city", "weather location unavailable");
        }, error => {
            if (coords !== loc || !GlobalConfig.services.weatherEnabled)
                return;
            console.warn(lc, `Nominatim request failed: ${error}`);
            city = Tr.trCtx("Unknown city", "weather location unavailable");
        }, nominatimHeaders);
    }

    function fetchCoordsFromCity(cityName: string): void {
        if (cityRequestPending)
            return;
        cityRequestPending = true;
        const generation = locationGeneration;
        const lang = citySearchLanguage(cityName);
        const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(cityName)}&count=1&language=${lang}&format=json`;

        Requests.get(url, text => {
            cityRequestPending = false;
            if (obsoleteRequest(generation))
                return;
            try {
                const json = JSON.parse(text);
                if (json.results && json.results.length > 0) {
                    const result = json.results[0];
                    if (!Number.isFinite(result.latitude) || !Number.isFinite(result.longitude))
                        throw new Error("invalid coordinates");
                    loc = result.latitude + "," + result.longitude;
                    city = fixCityName(result.name);
                    fetchWeatherData();
                } else {
                    error = Tr.tr("Weather location not found");
                }
            } catch (err) {
                root.fail(Tr.tr("Unable to determine weather location"));
            }
        }, err => {
            cityRequestPending = false;
            if (!obsoleteRequest(generation))
                root.fail(Tr.tr("Unable to determine weather location"));
        });
    }

    function fetchWeatherData(): void {
        const url = getWeatherUrl();
        if (url === "" || !GlobalConfig.services.weatherEnabled || weatherRequestPending)
            return;
        weatherRequestPending = true;
        const requestedLocation = loc, requestedProvider = provider, generation = locationGeneration;

        Requests.get(url, text => {
            weatherRequestPending = false;
            if (obsoleteRequest(generation) || requestedLocation !== loc || requestedProvider !== provider)
                return;
            try {
                const data = WeatherData.parse(requestedProvider, JSON.parse(text), new Date());
                cc = data.current;
                forecast = data.forecast.map(day => Object.assign({icon:Icons.getWeatherIcon(day.weatherCode)}, day));
                hourlyForecast = data.hourly.map(hour => Object.assign({icon:Icons.getWeatherIcon(hour.weatherCode)}, hour));
                error = "";
                retryTimer.stop();
            } catch (err) {
                console.warn(lc, `Unable to read weather forecast: ${err}`);
                root.fail(Tr.tr("Unable to load weather"));
            }
        }, err => {
            weatherRequestPending = false;
            if (!obsoleteRequest(generation) && requestedLocation === loc && requestedProvider === provider) {
                console.warn(lc, `Weather request failed (${requestedProvider}): ${err}`);
                root.fail(Tr.tr("Unable to load weather"));
            }
        });
    }

    function getWeatherUrl(): string {
        if (!loc || loc.indexOf(",") === -1)
            return "";

        const [lat, lon] = loc.split(",").map(s => s.trim());
        if (provider === "wttr.in")
            return `https://wttr.in/${lat},${lon}?format=j1`;
        const baseUrl = "https://api.open-meteo.com/v1/forecast";
        const params = ["latitude=" + lat, "longitude=" + lon, "hourly=weather_code,temperature_2m,precipitation_probability", "daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset", "current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m", "timezone=auto", "forecast_days=7"];

        return baseUrl + "?" + params.join("&");
    }

    function resetForecast(): void {
        root.cc = null;
        root.forecast = [];
        root.hourlyForecast = [];
        root.error = "";
    }

    function getWeatherCondition(code: string): string {
        const conditions = {
            "0": Tr.tr("Clear"),
            "1": Tr.tr("Clear"),
            "2": Tr.tr("Partly cloudy"),
            "3": Tr.tr("Overcast"),
            "45": Tr.tr("Fog"),
            "48": Tr.tr("Fog"),
            "51": Tr.tr("Drizzle"),
            "53": Tr.tr("Drizzle"),
            "55": Tr.tr("Drizzle"),
            "56": Tr.tr("Freezing drizzle"),
            "57": Tr.tr("Freezing drizzle"),
            "61": Tr.tr("Light rain"),
            "63": Tr.tr("Rain"),
            "65": Tr.tr("Heavy rain"),
            "66": Tr.tr("Light rain"),
            "67": Tr.tr("Heavy rain"),
            "71": Tr.tr("Light snow"),
            "73": Tr.tr("Snow"),
            "75": Tr.tr("Heavy snow"),
            "77": Tr.tr("Snow"),
            "80": Tr.tr("Light rain"),
            "81": Tr.tr("Rain"),
            "82": Tr.tr("Heavy rain"),
            "85": Tr.tr("Light snow showers"),
            "86": Tr.tr("Heavy snow showers"),
            "95": Tr.tr("Thunderstorm"),
            "96": Tr.tr("Thunderstorm with hail"),
            "99": Tr.tr("Thunderstorm with hail")
        };
        return conditions[code] || Tr.trCtx("Unknown", "weather condition");
    }

    onLocChanged: fetchWeatherData()
    onCitiesLoadedChanged: {
        if (!citiesLoaded || !pendingCoords)
            return;

        const coords = pendingCoords;
        pendingCoords = "";
        fetchCityFromCoords(coords);
    }

    Connections {
        function onWeatherEnabledChanged(): void {
            root.locationGeneration++;
            root.reload();
        }
        function onWeatherLocationChanged(): void {
            root.locationGeneration++;
            root.loc = "";
            root.city = "";
            root.resetForecast();
            retryTimer.restart();
            root.reload();
        }
        function onWeatherProviderChanged(): void {
            root.locationGeneration++;
            root.resetForecast();
            root.reload();
        }
        function onWeatherLocationNameChanged(): void {
            if (GlobalConfig.services.weatherLocation.trim() && GlobalConfig.services.weatherLocationName)
                root.city = GlobalConfig.services.weatherLocationName;
        }

        target: GlobalConfig.services
    }

    Timer {
        interval: 3600000 // 1 hour
        running: GlobalConfig.services.weatherEnabled
        repeat: true
        onTriggered: reload()
    }

    Timer {
        id: retryTimer
        interval: 60000
        onTriggered: root.reload()
    }

    Timer {
        id: ipApiRetryTimer

        repeat: false

        onTriggered: {
            const remaining = root.ipApiBlockedUntil - Date.now();

            if (remaining > 0) {
                interval = Math.ceil(remaining);
                restart();
            } else {
                root.reload();
            }
        }
    }

    Timer {
        id: citiesSaveTimer

        interval: 1000
        onTriggered: {
            if (!root.citiesLoaded)
                return;

            const data = {};
            root.cachedCities.forEach((cityName, coords) => data[coords] = cityName);
            citiesStorage.setText(JSON.stringify(data));
        }
    }

    ElapsedTimer {
        id: timer
    }

    FileView {
        id: citiesStorage

        printErrors: false
        path: `${Paths.cache}/cities.json`
        onLoaded: {
            try {
                const data = JSON.parse(text());
                for (const [coords, cityName] of Object.entries(data))
                    if (!root.cachedCities.has(coords))
                        root.cachedCities.set(coords, cityName);
            } catch (error) {
                console.warn(lc, `Unable to parse cached cities: ${error}`);
            }

            root.citiesLoaded = true;
        }
        onLoadFailed: err => {
            root.citiesLoaded = true;
            if (err === FileViewError.FileNotFound)
                Qt.callLater(() => setText("{}"));
            else
                console.warn(lc, `Unable to load cached cities: ${err}`);
        }
    }

    LoggingCategory {
        id: lc

        name: "hyprstack.qml.services.weather"
        defaultLogLevel: LoggingCategory.Info
    }
}
