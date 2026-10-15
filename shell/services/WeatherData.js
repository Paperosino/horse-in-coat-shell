// Both providers use the same units and WMO condition codes inside the shell.
function number(value) {
    if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value)))
        throw new Error("invalid weather measurement");
    return Number(value);
}

function parseOpenMeteo(json, now) {
    if (!json.current || !json.daily || !json.hourly || !json.daily.time?.length
        || !json.daily.sunrise?.length || !json.daily.sunset?.length)
        throw new Error("incomplete weather response");
    const current = {
        weatherCode: number(json.current.weather_code),
        tempC: number(json.current.temperature_2m),
        feelsLikeC: number(json.current.apparent_temperature),
        humidity: number(json.current.relative_humidity_2m),
        windSpeed: number(json.current.wind_speed_10m),
        isDay: number(json.current.is_day),
        sunrise: json.daily.sunrise[0].replace("T", " "),
        sunset: json.daily.sunset[0].replace("T", " ")
    };
    const forecast = json.daily.time.map((date, i) => ({
        date: date.replace(/-/g, "/"),
        maxTempC: number(json.daily.temperature_2m_max[i]),
        minTempC: number(json.daily.temperature_2m_min[i]),
        weatherCode: number(json.daily.weather_code[i])
    }));
    const hourly = [];
    for (let i = 0; i < json.hourly.time.length; i++) {
        const timestamp = json.hourly.time[i];
        const time = new Date(timestamp.replace("T", " "));
        if (!Number.isFinite(time.getTime()))
            throw new Error("invalid forecast time");
        if (time < now)
            continue;
        hourly.push({timestamp, hour: time.getHours(),
            tempC: Math.round(number(json.hourly.temperature_2m[i])),
            precipChance: number(json.hourly.precipitation_probability[i]),
            weatherCode: number(json.hourly.weather_code[i])});
    }
    return {current, forecast, hourly};
}

function wttrCode(value) {
    const codes = {
        113:0, 116:2, 119:3, 122:3, 143:45, 176:61, 179:71, 182:66, 185:56,
        200:95, 227:75, 230:75, 248:45, 260:48, 263:51, 266:51, 281:56, 284:57,
        293:61, 296:61, 299:63, 302:63, 305:65, 308:65, 311:66, 314:67,
        317:66, 320:67, 323:71, 326:71, 329:73, 332:73, 335:75, 338:75, 350:77,
        353:80, 356:81, 359:82, 362:66, 365:67, 368:85, 371:86, 374:77, 377:77,
        386:95, 389:95, 392:95, 395:95
    };
    return codes[value] ?? -1;
}

function astronomyTime(date, value) {
    const match = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i.exec(value ?? "");
    if (!match)
        return null;
    const hour = Number(match[1]) % 12 + (match[3].toUpperCase() === "PM" ? 12 : 0);
    return date + " " + String(hour).padStart(2, "0") + ":" + match[2];
}

function parseWttr(json, now) {
    if (!json.current_condition?.length || !json.weather?.length)
        throw new Error("incomplete weather response");
    const observation = json.current_condition[0], today = json.weather[0];
    const sunrise = astronomyTime(today.date, today.astronomy?.[0]?.sunrise);
    const sunset = astronomyTime(today.date, today.astronomy?.[0]?.sunset);
    const current = {
        weatherCode: wttrCode(observation.weatherCode),
        tempC: number(observation.temp_C), feelsLikeC: number(observation.FeelsLikeC),
        humidity: number(observation.humidity), windSpeed: number(observation.windspeedKmph),
        isDay: sunrise && sunset && now >= new Date(sunrise) && now < new Date(sunset) ? 1 : 0,
        sunrise, sunset
    };
    const forecast = [], hourly = [];
    for (const day of json.weather) {
        if (!day.hourly?.length || !/^\d{4}-\d{2}-\d{2}$/.test(day.date))
            throw new Error("incomplete daily forecast");
        // A midday sample represents the day without depending on the first midnight interval.
        const noon = day.hourly.reduce((best, sample) =>
            Math.abs(Number(sample.time) - 1200) < Math.abs(Number(best.time) - 1200) ? sample : best);
        forecast.push({date:day.date.replace(/-/g,"/"), maxTempC:number(day.maxtempC),
            minTempC:number(day.mintempC), weatherCode:wttrCode(noon.weatherCode)});
        for (const sample of day.hourly) {
            const hour = Math.floor(number(sample.time) / 100);
            if (hour < 0 || hour > 23)
                throw new Error("invalid forecast hour");
            const timestamp = day.date + "T" + String(hour).padStart(2,"0") + ":00";
            if (new Date(timestamp.replace("T"," ")) < now)
                continue;
            hourly.push({timestamp, hour, tempC:Math.round(number(sample.tempC)),
                precipChance:Math.max(number(sample.chanceofrain),number(sample.chanceofsnow)),
                weatherCode:wttrCode(sample.weatherCode)});
        }
    }
    return {current, forecast, hourly};
}

function parse(provider, json, now) {
    return provider === "wttr.in" ? parseWttr(json, now) : parseOpenMeteo(json, now);
}
