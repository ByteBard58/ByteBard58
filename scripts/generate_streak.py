import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# Configuration
USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER")
TOKEN = os.getenv("GITHUB_TOKEN")
OUTPUT_PATH = "profile/streak.svg"

# Onedark Theme Colors
COLORS = {
    "bg": "#282c34",
    "border": "#e4e2e2",
    "header": "#e4bf7a",
    "stat": "#df6d74",
    "label_green": "#8eb573",
    "label_yellow": "#e4bf7a",
    "text_white": "#abb2bf"
}

def format_iso8601(dt):
    """Formats a datetime object to the ISO 8601 string GitHub expects."""
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def graphql_query(query, variables):
    """Executes a GraphQL query and returns the JSON response."""
    if not TOKEN:
        raise Exception("GITHUB_TOKEN is not set.")
        
    req_data = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=req_data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "ByteBard58-Streak-Action"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            if "errors" in res_json:
                print(f"GraphQL Errors encountered for query: {variables}")
                for error in res_json["errors"]:
                    print(f" - {error.get('message')}")
                # We return it anyway, the caller will handle missing 'data'
            return res_json
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Response body: {e.read().decode('utf-8')}")
        raise
    except Exception as e:
        print(f"Unexpected error during API call: {e}")
        raise

def get_user_data():
    """Initial query to get creation date and recent contributions."""
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
    if not res or "data" not in res or not res["data"].get("user"):
        raise Exception(f"Failed to fetch user data. Response: {res}")
    return res["data"]["user"]

def get_all_time_contributions(created_at_str):
    """Calculates total contributions across all years since account creation."""
    # Parse creation date correctly (Z -> +00:00 for fromisoformat)
    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total = 0
    
    start_year = created_at.year
    current_year = now.year
    
    print(f"Fetching contributions from {start_year} to {current_year}...")
    
    for year in range(start_year, current_year + 1):
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
        # Define ranges for each year chunk
        year_start = max(created_at, datetime(year, 1, 1, tzinfo=timezone.utc))
        year_end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        
        variables = {
            "userName": USERNAME,
            "from": format_iso8601(year_start),
            "to": format_iso8601(year_end)
        }
        
        res = graphql_query(query, variables)
        
        try:
            year_total = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
            total += year_total
            print(f" - Year {year}: {year_total} contributions")
        except (KeyError, TypeError) as e:
            print(f"Warning: Could not fetch contributions for {year}. Skipping. Error: {e}")
            if res:
                print(f" Raw response: {res}")
        
    return total

def calculate_streaks(weeks):
    """Calculates streaks and their date ranges from contribution weeks."""
    all_days = []
    for week in weeks:
        for day in week["contributionDays"]:
            all_days.append(day)
    
    all_days.sort(key=lambda x: x["date"])
    
    current_streak = 0
    longest_streak = 0
    
    longest_streak_start = ""
    longest_streak_end = ""
    
    temp_streak = 0
    temp_start = ""
    
    # Calculate longest streak across history
    for day in all_days:
        if day["contributionCount"] > 0:
            if temp_streak == 0:
                temp_start = day["date"]
            temp_streak += 1
            if temp_streak >= longest_streak:
                longest_streak = temp_streak
                longest_streak_start = temp_start
                longest_streak_end = day["date"]
        else:
            temp_streak = 0
            
    # Calculate current streak ending today/yesterday
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    yesterday_str = (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    
    current_streak_start = ""
    current_streak_end = ""
    
    last_contrib_day = None
    for day in reversed(all_days):
        if day["contributionCount"] > 0:
            last_contrib_day = day["date"]
            break
            
    if last_contrib_day in [today_str, yesterday_str]:
        count = 0
        counting = False
        current_streak_end = last_contrib_day
        for day in reversed(all_days):
            if day["date"] == last_contrib_day:
                counting = True
            if counting:
                if day["contributionCount"] > 0:
                    count += 1
                    current_streak_start = day["date"]
                else:
                    break
        current_streak = count
        
    return {
        "current": {"count": current_streak, "start": current_streak_start, "end": current_streak_end},
        "longest": {"count": longest_streak, "start": longest_streak_start, "end": longest_streak_end}
    }

def format_date_range(start_str, end_str):
    """Formats a date range string for the SVG."""
    if not start_str or not end_str:
        return "No contributions"
    start_dt = datetime.fromisoformat(start_str)
    end_dt = datetime.fromisoformat(end_str)
    
    # DenverCoder1 style: Omit year if same year
    if start_dt.year == end_dt.year:
        return f"{start_dt.strftime('%b %-d')} - {end_dt.strftime('%b %-d')}"
    return f"{start_dt.strftime('%b %-d, %Y')} - {end_dt.strftime('%b %-d, %Y')}"

def generate_svg(total_commits, current_streak_data, longest_streak_data, start_date_str):
    """Generates the SVG source with specified stats and colors."""
    start_date_obj = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
    start_date_fmt = start_date_obj.strftime("%b %-d, %Y")
    
    current_range = format_date_range(current_streak_data["start"], current_streak_data["end"])
    longest_range = format_date_range(longest_streak_data["start"], longest_streak_data["end"])
    
    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
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
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>{total_commits}</text>
                </g>
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>Total Contributions</text>
                </g>
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["stat"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>{start_date_fmt} - Present</text>
                </g>
            </g>

            <!-- Current Streak -->
            <g style='isolation: isolate'>
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["label_green"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='animation: currstreak 0.6s linear forwards'>{current_streak_data["count"]}</text>
                </g>
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["label_green"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>Current Streak</text>
                </g>
                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' stroke-width='0' text-anchor='middle' fill='{COLORS["stat"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>{current_range}</text>
                </g>
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='{COLORS["header"]}' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <g transform='translate(247.5, 19.5)' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='{COLORS["header"]}'/>
                </g>
            </g>

            <!-- Longest Streak -->
            <g style='isolation: isolate'>
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>{longest_streak_data["count"]}</text>
                </g>
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["header"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>Longest Streak</text>
                </g>
                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{COLORS["stat"]}' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>{longest_range}</text>
                </g>
            </g>
        </g>
    </svg>"""

def main():
    print(f"Starting streak generation for {USERNAME}...")
    if not TOKEN:
        print("GITHUB_TOKEN not set. Exiting.")
        return

    try:
        user_data = get_user_data()
        created_at = user_data["createdAt"]
        
        # Absolute total commits
        total_commits = get_all_time_contributions(created_at)
        
        # Streak calculation
        streaks = calculate_streaks(user_data["contributionsCollection"]["contributionCalendar"]["weeks"])
        
        svg_content = generate_svg(total_commits, streaks["current"], streaks["longest"], created_at)
        
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            f.write(svg_content)
        
        print(f"Success! Generated {OUTPUT_PATH}")
        print(f" - Total Commits: {total_commits}")
        print(f" - Current Streak: {streaks['current']['count']} ({streaks['current']['start']} to {streaks['current']['end']})")
        print(f" - Longest Streak: {streaks['longest']['count']} ({streaks['longest']['start']} to {streaks['longest']['end']})")

    except Exception as e:
        print(f"Error: Automation failed: {e}")
        # We exit with 1 to let the CI know it failed, but we printed instructions above
        exit(1)

if __name__ == "__main__":
    main()
