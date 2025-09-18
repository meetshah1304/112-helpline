# modules/ui_calendar.py
import calendar
from datetime import date

def render_month_calendar(year: int, month: int, festival_dates_map: dict) -> str:
    """
    Render an HTML calendar for the given month with highlighted festival days.
    festival_dates_map: dict mapping 'YYYY-MM-DD' -> list of festival names
    """
    cal = calendar.Calendar(firstweekday=0)
    month_days = list(cal.itermonthdates(year, month))

    html = """
    <style>
    .calendar {font-family: Arial, sans-serif; border-collapse: collapse; width: 100%;}
    .calendar th {background: #f2f2f2; padding: 6px; text-align: center; color:#222;}
    .calendar td {width: 14%; height: 64px; text-align: center; vertical-align: top; border: 1px solid #eee; padding: 6px; font-size: 12px; color:#222;}
    .other-month {color: #bbb;}
    .fest-day {position:relative;}
    .fest-circle {
        display:inline-block;
        width:28px;
        height:28px;
        border-radius:50%;
        background: #ffea75; /* pale yellow */
        border: 2px solid #e6c200;
        line-height:28px;
        font-weight:700;
        color:#333;
    }
    .fest-names {display:block; font-size:10px; color:#444; padding-top:4px; max-height:32px; overflow:hidden;}
    </style>
    """

    html += f"<table class='calendar'>"
    html += f"<tr><th colspan='7' style='font-size:14px;padding:8px'>{calendar.month_name[month]} {year}</th></tr>"
    html += "<tr>" + "".join([f"<th style='padding:6px'>{d}</th>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) + "</tr><tr>"

    week_day_count = 0
    for day in month_days:
        classes = []
        cell_inner = ""
        iso = day.isoformat()
        # day number
        day_num = str(day.day)
        if day.month != month:
            classes.append("other-month")
        if iso in festival_dates_map:
            # highlight with yellow circle and show short festival name(s)
            fest_names = ", ".join(festival_dates_map[iso])
            # truncate
            if len(fest_names) > 20:
                fest_short = fest_names[:20] + "..."
            else:
                fest_short = fest_names
            cell_inner = f"<div class='fest-day'><span class='fest-circle'>{day_num}</span><div class='fest-names' title='{fest_names}'>{fest_short}</div></div>"
        else:
            cell_inner = f"<div>{day_num}</div>"

        html += f"<td class='{' '.join(classes)}'>{cell_inner}</td>"
        week_day_count += 1
        if week_day_count == 7:
            html += "</tr><tr>"
            week_day_count = 0

    html += "</tr></table>"
    return html
