import os
import json
import urllib.request
from datetime import datetime, timedelta

# Configuration
USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER")
TOKEN = os.getenv("GITHUB_TOKEN")
OUTPUT_PATH = "profile/streak.svg"

# Onedark Theme Colors (Matching the ones seen in the user's profile and samples)
COLORS = {
    "bg": "#282c34",
    "border": "#e4e2e2",
    "header": "#e4bf7a",
    "stat": "#df6d74",
    "label_green": "#8eb573",
    "label_yellow": "#e4bf7a",
    "text_white": "#abb2bf"
}

def graphql_query(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

def get_user_data():
    # Initial query to get creation date and some recent history
    query = """
    query($userName:String!) {
      user(login: $userName) {
        createdAt
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    res = graphql_query(query, {"userName": USERNAME})
    if "errors" in res:
        raise Exception(f"GraphQL Errors: {res['errors']}")
    return res["data"]["user"]

def get_all_time_contributions(created_at_str):
    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    now = datetime.utcnow()
    total = 0
    
    # We fetch yearly chunks to get the absolute total
    # This is more robust for "universal count"
    current_year = now.year
    start_year = created_at.year
    
    for year in range(start_year, current_year + 1):
        # We use from/to to get chunks
        query = """
        query($userName:String!, $from:DateTime!, $to:DateTime!) {
          user(login: $userName) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                totalContributions
              }
            }
          }
        }
        """
        # Define the range for the year
        # Start of year or account creation date
        year_start = max(created_at, datetime(year, 1, 1))
        # End of year or now
        year_end = min(now, datetime(year, 12, 31, 23, 59, 59))
        
        variables = {
            "userName": USERNAME,
            "from": year_start.isoformat() + "Z",
            "to": year_end.isoformat() + "Z"
        }
        res = graphql_query(query, variables)
        total += res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        
    return total

def calculate_streaks(weeks):
    # Flatten days
    all_days = []
    for week in weeks:
        for day in week["contributionDays"]:
            all_days.append(day)
    
    # Sort by date
    all_days.sort(key=lambda x: x["date"])
    
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    
    # We check from the end for current streak
    # streaks are calculated based on consecutive days with count > 0
    
    # First, find streaks in the entire history provided (last year +)
    for i, day in enumerate(all_days):
        if day["contributionCount"] > 0:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 0
            
    # For current streak, check if today or yesterday had contributions
    # Use the end of the list
    current_streak = 0
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Check if the last day is today or yesterday
    last_contrib_day = None
    for day in reversed(all_days):
        if day["contributionCount"] > 0:
            last_contrib_day = day["date"]
            break
            
    if last_contrib_day in [today_str, yesterday_str]:
        # Count backwards from the last contributed day
        count = 0
        counting = False
        for day in reversed(all_days):
            if day["date"] == last_contrib_day:
                counting = True
            if counting:
                if day["contributionCount"] > 0:
                    count += 1
                else:
                    break
        current_streak = count
        
    return current_streak, longest_streak

def generate_svg(total_commits, current_streak, longest_streak, start_date_str):
    # Date formatting
    start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00")).strftime("%b %-d, %Y")
    now_str = datetime.utcnow().strftime("%b %-d, %Y")
    
    # This matches the layout of the streak-stats.demolab.com
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 28px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='7.5'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='{COLORS["border"]}' fill='{COLORS["bg"]}' rx='7.5' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='{COLORS["border"]}' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='{COLORS["border"]}' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            
            <!-- Total Contributions -->
            <g style='isolation: isolate'>
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                        {total_commits}
                    </text>
                </g>
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>
                        Total Contributions
                    </text>
                </g>
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["stat"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>
                        {start_date} - Present
                    </text>
                </g>
            </g>

            <!-- Current Streak -->
            <g style='isolation: isolate'>
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["label_green"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        Current Streak
                    </text>
                </g>
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='{COLORS["header"]}' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='{COLORS["header"]}' stroke-opacity='0'/>
                </g>
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["label_green"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='animation: currstreak 0.6s linear forwards'>
                        {current_streak}
                    </text>
                </g>
            </g>

            <!-- Longest Streak -->
            <g style='isolation: isolate'>
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>
                        {longest_streak}
                    </text>
                </g>
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>
                        Longest Streak
                    </text>
                </g>
            </g>
        </g>
    </svg>"""
    return svg

def main():
    if not TOKEN:
        # For local testing, if no token, just exit
        print("GITHUB_TOKEN not set. Skipping.")
        return

    data = get_user_data()
    created_at = data["createdAt"]
    
    # Universal count
    total_commits = get_all_time_contributions(created_at)
    
    # Streak calculation (using the last 400 days to be safe)
    # The get_user_data already gives current weeks.
    current_streak, longest_streak = calculate_streaks(data["contributionsCollection"]["contributionCalendar"]["weeks"])
    
    svg_content = generate_svg(total_commits, current_streak, longest_streak, created_at)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, "w") as f:
        f.write(svg_content)
    
    print(f"Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
