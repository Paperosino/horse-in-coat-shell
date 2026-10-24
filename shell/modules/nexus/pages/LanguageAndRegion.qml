import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "language"

    property bool cityMode: GlobalConfig.services.weatherLocation.trim().length > 0
    property string cityQuery
    property string searchedCityQuery
    property var cityResults: []
    property bool citySearchLoading
    property string citySearchError
    property int citySearchGeneration

    readonly property list<MenuItem> weatherProviderItems: [
        MenuItem {
            text: "Open-Meteo"
            value: "open-meteo"
        },
        MenuItem {
            text: "wttr.in"
            value: "wttr.in"
        }
    ]
    readonly property list<MenuItem> weatherLocationItems: [
        MenuItem {
            text: Tr.tr("Automatic by IP")
            value: "ip"
        },
        MenuItem {
            text: Tr.tr("City")
            value: "city"
        }
    ]

    function updateCityQuery(value: string): void {
        cityQuery = value;
        searchedCityQuery = "";
        citySearchGeneration++;
        cityResults = [];
        citySearchError = "";
        citySearchLoading = false;
        if (value.trim().length >= 2)
            citySearchTimer.restart();
        else
            citySearchTimer.stop();
    }

    function searchCities(): void {
        const query = cityQuery.trim();
        if (query.length < 2 || query === searchedCityQuery)
            return;
        searchedCityQuery = query;
        citySearchLoading = true;
        citySearchError = "";
        const generation = ++citySearchGeneration;
        Weather.searchCities(query, results => {
            if (!root || generation !== root.citySearchGeneration)
                return;
            root.citySearchLoading = false;
            root.cityResults = results;
            root.citySearchError = results.length ? "" : Tr.tr("No matching cities");
        }, error => {
            if (!root || generation !== root.citySearchGeneration)
                return;
            root.citySearchLoading = false;
            root.searchedCityQuery = "";
            root.citySearchError = error;
        });
    }

    function chooseCity(result: var): void {
        citySearchTimer.stop();
        citySearchGeneration++;
        citySearchLoading = false;
        cityResults = [];
        citySearchError = "";
        Weather.selectCity(result);
        cityField.clear();
        cityQuery = "";
    }

    readonly property Timer citySearchTimer: Timer {
        id: citySearchTimer
        interval: 400
        onTriggered: root.searchCities()
    }

    readonly property Connections weatherLocationConnection: Connections {
        target: GlobalConfig.services
        function onWeatherLocationChanged(): void {
            root.cityMode = GlobalConfig.services.weatherLocation.trim().length > 0;
        }
    }

    Component.onDestruction: citySearchGeneration++

    // Temperature units (there must be one for each value of the TemperatureUnit enum)
    readonly property list<MenuItem> tempItems: [
        MenuItem {
            text: Tr.tr("Auto")
            value: TemperatureUnit.Auto
        },
        MenuItem {
            text: Tr.tr("°C")
            value: TemperatureUnit.Celsius
        },
        MenuItem {
            text: Tr.tr("°F")
            value: TemperatureUnit.Fahrenheit
        },
        MenuItem {
            text: Tr.tr("K")
            value: TemperatureUnit.Kelvin
        }
    ]

    // Data size units (there must be one for each value of the DataUnit enum)
    readonly property list<MenuItem> dataItems: [
        MenuItem {
            text: Tr.tr("Binary (KiB, MiB)")
            value: DataUnit.Binary
        },
        MenuItem {
            text: Tr.tr("Decimal (KB, MB)")
            value: DataUnit.Decimal
        }
    ]

    // Clock formats (there must be one for each value of the ClockFormat enum)
    readonly property list<MenuItem> clockItems: [
        MenuItem {
            text: Tr.tr("Auto")
            value: ClockFormat.Auto
        },
        MenuItem {
            text: Tr.tr("12-hour")
            value: ClockFormat.TwelveHour
        },
        MenuItem {
            text: Tr.tr("24-hour")
            value: ClockFormat.TwentyFourHour
        }
    ]

    title: Tr.tr("Language & region")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        RegionSection {}
        // Language
        SettingsCard {
            title: Tr.tr("Language")
            icon: "language"

            SelectRow {
                objectName: "uiLanguage"
                first: true
                last: true
                label: Tr.tr("UI language")
                subtext: Tr.tr("The language used in the shell UI")
                active: GlobalConfig.general.language ? menuItems.find(i => i.modelData === Tr.language) ?? autoLang : autoLang
                onSelected: item => {
                    Tr.language = item.modelData ?? ""; // qmllint disable missing-property
                }

                menuItems: [autoLang, ...langItems.instances]

                MenuItem {
                    id: autoLang

                    text: Tr.tr("System language")
                }

                Variants {
                    id: langItems

                    model: Tr.supportedLanguages

                    MenuItem {
                        required property string modelData

                        text: {
                            if (modelData === "ru_RU")
                                return "Русский";
                            if (modelData === "en_US")
                                return "English";
                            const locale = Qt.locale(modelData);
                            return locale.name === "C" ? modelData : locale.nativeLanguageName || locale.name;
                        }
                    }
                }
            }

            // Weather
        }
        SettingsCard {
            title: Tr.tr("Weather")
            icon: "language"

            ToggleRow {
                objectName: "weatherEnabled"
                first: true
                text: Tr.tr("Enable weather")
                checked: GlobalConfig.services.weatherEnabled
                onToggled: GlobalConfig.services.weatherEnabled = checked
            }

            SelectRow {
                objectName: "weatherProvider"
                label: Tr.tr("Weather provider")
                subtext: Weather.provider === "wttr.in" ? Tr.tr("3-day forecast, every 3 hours") : Tr.tr("7-day forecast, hourly")
                menuItems: root.weatherProviderItems
                active: root.weatherProviderItems.find(item => item.value === Weather.provider)
                onSelected: item => GlobalConfig.services.weatherProvider = item.value
            }

            SelectRow {
                objectName: "weatherLocation"
                label: Tr.tr("Weather location")
                subtext: root.cityMode ? Tr.tr("Choose a city below") : Tr.tr("Determine the city from your public IP address")
                menuItems: root.weatherLocationItems
                active: root.weatherLocationItems.find(item => item.value === (root.cityMode ? "city" : "ip"))
                onSelected: item => {
                    root.cityMode = item.value === "city";
                    if (!root.cityMode) {
                        citySearchTimer.stop();
                        root.citySearchGeneration++;
                        root.citySearchLoading = false;
                        root.cityResults = [];
                        root.citySearchError = "";
                        root.cityQuery = "";
                        cityField.clear();
                        Weather.useAutomaticLocation();
                    } else {
                        cityField.field.forceActiveFocus();
                    }
                }
            }

            InfoRow {
                visible: root.cityMode && GlobalConfig.services.weatherLocation.trim().length > 0
                label: Tr.tr("Selected city")
                value: GlobalConfig.services.weatherLocationLabel || GlobalConfig.services.weatherLocationName || Weather.city || GlobalConfig.services.weatherLocation
            }

            TextFieldRow {
                id: cityField
                objectName: "weatherCitySearch"
                visible: root.cityMode
                label: Tr.tr("Weather city")
                subtext: Tr.tr("Enter a name and select a city from the results")
                placeholderText: Tr.tr("City name")
                onValueEdited: value => root.updateCityQuery(value)
                onEditingFinished: value => {
                    citySearchTimer.stop();
                    root.searchCities();
                }
            }

            StyledText {
                Layout.fillWidth: true
                Layout.leftMargin: Tokens.padding.largeIncreased
                Layout.rightMargin: Tokens.padding.largeIncreased
                Layout.topMargin: Tokens.padding.small
                Layout.bottomMargin: Tokens.padding.small
                visible: root.cityMode && (root.citySearchLoading || root.citySearchError || root.cityQuery.trim().length < 2)
                text: root.citySearchLoading ? Tr.tr("Searching for cities…") : root.citySearchError || Tr.tr("Enter at least two characters to search")
                color: root.citySearchError ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                wrapMode: Text.WordWrap
            }

            Repeater {
                model: root.cityMode ? root.cityResults : []

                RowButton {
                    required property var modelData
                    required property int index
                    objectName: "weatherCityResult_" + index
                    text: modelData.name
                    subtext: modelData.label
                    icon: "location_city"
                    onClicked: root.chooseCity(modelData)
                }
            }

            InfoRow {
                label: Tr.tr("Current weather location")
                value: Weather.loading ? Tr.tr("Loading weather…") : Weather.error || Weather.city || Tr.tr("Automatic by IP")
            }

            RowButton {
                objectName: "weatherRefresh"
                last: true
                text: Tr.tr("Refresh weather")
                disabled: !GlobalConfig.services.weatherEnabled || Weather.loading
                onClicked: Weather.reload()
            }

            // Units
        }
        SettingsCard {
            title: Tr.tr("Units")
            icon: "language"

            SelectRow {
                first: true
                label: Tr.tr("Temperature")
                subtext: Tr.tr("Units for weather temperatures")
                menuItems: root.tempItems
                active: root.tempItems.find(i => i.value === GlobalConfig.services.weatherUnits)
                onSelected: item => GlobalConfig.services.weatherUnits = item.value
            }

            SelectRow {
                label: Tr.tr("System temperatures")
                subtext: Tr.tr("Units for CPU and GPU temperatures")
                menuItems: root.tempItems
                active: root.tempItems.find(i => i.value === GlobalConfig.services.sensorUnits)
                onSelected: item => GlobalConfig.services.sensorUnits = item.value
            }

            SelectRow {
                last: true
                label: Tr.tr("Data sizes")
                subtext: Tr.tr("Units for data sizes and network speeds")
                menuItems: root.dataItems
                active: root.dataItems.find(i => i.value === GlobalConfig.services.dataUnits)
                onSelected: item => GlobalConfig.services.dataUnits = item.value
            }

            // Time & date
        }
        SettingsCard {
            title: Tr.tr("Time & date")
            icon: "language"

            SelectRow {
                first: true
                last: true
                label: Tr.tr("Clock format")
                subtext: Tr.tr("How times are shown across the shell")
                menuOnTop: true
                menuItems: root.clockItems
                active: root.clockItems.find(i => i.value === GlobalConfig.services.clockFormat)
                onSelected: item => GlobalConfig.services.clockFormat = item.value
            }
        }
    }
}
