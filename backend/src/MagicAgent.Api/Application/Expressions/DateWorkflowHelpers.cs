using System;
using System.Globalization;

namespace MagicAgent.Api.Application.Expressions.Helpers;

public static class DateWorkflowHelpers
{
    [WorkflowHelper("dateAdd", ReturnType = WorkflowExpressionValueKind.String, Description = "Adds or subtracts an interval from a date (ISO 8601 result).")]
    [WorkflowHelperParameter("baseDate", Description = "Base date/time value.")]
    [WorkflowHelperParameter("amount", Description = "Amount to add (negative to subtract).")]
    [WorkflowHelperParameter("unit", Description = "Interval unit (years, months, days, hours, minutes).", IsOptional = true)]
    public static string DateAdd(string baseDate, double amount, string unit)
    {
        var date = ParseDate(baseDate, nameof(baseDate));
        var normalizedUnit = NormalizeUnit(unit);

        var result = normalizedUnit switch
        {
            "year" or "years" => date.AddYears((int)Math.Truncate(amount)),
            "month" or "months" => date.AddMonths((int)Math.Truncate(amount)),
            "hour" or "hours" => date.AddHours(amount),
            "minute" or "minutes" or "min" or "mins" => date.AddMinutes(amount),
            _ => date.AddDays(amount),
        };

        return FormatIso(result);
    }

    [WorkflowHelper("dateDiff", ReturnType = WorkflowExpressionValueKind.Number, Description = "Calculates the difference between two dates in the requested unit.")]
    [WorkflowHelperParameter("firstDate", Description = "Start/earlier date.")]
    [WorkflowHelperParameter("secondDate", Description = "End/later date.")]
    [WorkflowHelperParameter("unit", Description = "Difference unit (years, months, days, hours, minutes).", IsOptional = true)]
    public static double DateDiff(string firstDate, string secondDate, string unit)
    {
        var start = ParseDate(firstDate, nameof(firstDate));
        var end = ParseDate(secondDate, nameof(secondDate));
        var normalized = NormalizeUnit(unit);
        var span = end - start;

        return normalized switch
        {
            "year" or "years" => CalculateYearDifference(start, end),
            "month" or "months" => CalculateMonthDifference(start, end),
            "hour" or "hours" => span.TotalHours,
            "minute" or "minutes" or "min" or "mins" => span.TotalMinutes,
            _ => span.TotalDays,
        };
    }

    [WorkflowHelper("dayOfWeek", ReturnType = WorkflowExpressionValueKind.String, Description = "Returns the localized day-of-week name for the provided date.")]
    [WorkflowHelperParameter("date", Description = "Input date/time.")]
    [WorkflowHelperParameter("culture", Description = "Optional culture/language code (e.g. en, es, fr).", IsOptional = true)]
    public static string DayOfWeek(string date, string? culture = null)
    {
        var parsed = ParseDate(date, nameof(date));
        var cultureInfo = ResolveCulture(culture);
        return cultureInfo.DateTimeFormat.GetDayName(parsed.DayOfWeek);
    }

    [WorkflowHelper("toLocalDate", ReturnType = WorkflowExpressionValueKind.String, Description = "Converts a UTC date string to a local time using the provided offset (minutes).")]
    [WorkflowHelperParameter("utcDate", Description = "UTC date/time string.")]
    [WorkflowHelperParameter("offsetMinutes", Description = "Offset in minutes (positive/negative).")]
    public static string ToLocalDate(string utcDate, double offsetMinutes)
    {
        var utc = ParseDate(utcDate, nameof(utcDate)).ToUniversalTime();
        var offset = TimeSpan.FromMinutes(offsetMinutes);
        return FormatIso(utc.ToOffset(offset));
    }

    [WorkflowHelper("toDateUtc", ReturnType = WorkflowExpressionValueKind.String, Description = "Converts a local date/time to UTC (ISO 8601).")]
    [WorkflowHelperParameter("localDate", Description = "Local date/time string.")]
    [WorkflowHelperParameter("offsetMinutes", Description = "Offset applied to the local date (minutes).", IsOptional = true)]
    public static string ToDateUtc(string localDate, double offsetMinutes = 0)
    {
        var parsed = ParseDate(localDate, nameof(localDate));
        var normalized = Math.Abs(offsetMinutes) < double.Epsilon
            ? parsed
            : new DateTimeOffset(parsed.DateTime, TimeSpan.FromMinutes(offsetMinutes));

        return FormatIso(normalized.ToUniversalTime());
    }

    [WorkflowHelper("localOffset", ReturnType = WorkflowExpressionValueKind.Number, Description = "Returns the offset in minutes for the provided date/time string.")]
    [WorkflowHelperParameter("localDate", Description = "Local date/time string (may include offset).")]
    public static double LocalOffset(string localDate)
    {
        var parsed = ParseDate(localDate, nameof(localDate));
        return parsed.Offset.TotalMinutes;
    }

    [WorkflowHelper("dateConvert", ReturnType = WorkflowExpressionValueKind.String, Description = "Formats a date using the specified .NET format string.")]
    [WorkflowHelperParameter("date", Description = "Date/time to format.")]
    [WorkflowHelperParameter("format", Description = "Format string (defaults to ISO 'O').", IsOptional = true)]
    public static string DateConvert(string date, string format)
    {
        var parsed = ParseDate(date, nameof(date));
        var template = string.IsNullOrWhiteSpace(format) ? "O" : format;
        return parsed.ToString(template, CultureInfo.InvariantCulture);
    }

    [WorkflowHelper("stringToDate", ReturnType = WorkflowExpressionValueKind.DateTime, Description = "Parses a date string (optionally using format/culture) and returns a DateTime value.")]
    [WorkflowHelperParameter("value", Description = "Date/time string to parse.")]
    [WorkflowHelperParameter("format", Description = "Optional .NET format string to use when parsing.", IsOptional = true)]
    [WorkflowHelperParameter("culture", Description = "Optional culture name (e.g. en-US).", IsOptional = true)]
    public static DateTimeOffset StringToDate(string value, string? format = null, string? culture = null)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Parameter 'value' must contain a date/time string.", nameof(value));
        }

        var cultureInfo = ResolveCulture(culture);

        if (!string.IsNullOrWhiteSpace(format))
        {
            if (DateTimeOffset.TryParseExact(value, format, cultureInfo, DateTimeStyles.RoundtripKind, out var formatted))
            {
                return formatted;
            }

            throw new ArgumentException("Value does not match the provided format.", nameof(value));
        }

        if (DateTimeOffset.TryParse(value, cultureInfo, DateTimeStyles.RoundtripKind, out var parsed))
        {
            return parsed;
        }

        if (DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out parsed))
        {
            return parsed;
        }

        throw new ArgumentException("Value is not a valid date/time string.", nameof(value));
    }

    [WorkflowHelper("datePart", ReturnType = WorkflowExpressionValueKind.Number, Description = "Extracts a numeric component from a date.")]
    [WorkflowHelperParameter("date", Description = "Input date/time.")]
    [WorkflowHelperParameter("part", Description = "Part to extract (year, month, day, hour, minute).")]
    public static double DatePart(string date, string part)
    {
        var parsed = ParseDate(date, nameof(date));
        var normalized = NormalizeUnit(part);

        return normalized switch
        {
            "year" => parsed.Year,
            "month" => parsed.Month,
            "hour" or "hours" => parsed.Hour,
            "minute" or "minutes" or "min" => parsed.Minute,
            _ => parsed.Day,
        };
    }

    private static DateTimeOffset ParseDate(string value, string parameterName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException($"Parameter '{parameterName}' must contain a date/time value.", parameterName);
        }

        if (DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed))
        {
            return parsed;
        }

        if (DateTimeOffset.TryParse(value, CultureInfo.CurrentCulture, DateTimeStyles.RoundtripKind, out parsed))
        {
            return parsed;
        }

        throw new ArgumentException($"Parameter '{parameterName}' is not a valid date/time string.", parameterName);
    }

    private static string NormalizeUnit(string? value)
        => string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim().ToLowerInvariant();

    private static string FormatIso(DateTimeOffset value)
        => value.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);

    private static CultureInfo ResolveCulture(string? culture)
    {
        if (string.IsNullOrWhiteSpace(culture))
        {
            return CultureInfo.InvariantCulture;
        }

        try
        {
            return new CultureInfo(culture);
        }
        catch (CultureNotFoundException)
        {
            return CultureInfo.InvariantCulture;
        }
    }

    private static double CalculateYearDifference(DateTimeOffset start, DateTimeOffset end)
    {
        var years = end.Year - start.Year;
        var remainder = (end.DayOfYear - start.DayOfYear) / 365.0;
        return years + remainder;
    }

    private static double CalculateMonthDifference(DateTimeOffset start, DateTimeOffset end)
    {
        var months = (end.Year - start.Year) * 12 + (end.Month - start.Month);
        var remainder = (end.Day - start.Day) / 30.0;
        return months + remainder;
    }
}