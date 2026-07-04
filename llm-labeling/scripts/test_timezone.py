import uuid
from datetime import datetime

print("--- Timezone Resolution Test ---")

# 1. Attempt ZoneInfo
try:
    from zoneinfo import ZoneInfo
    berlin_tz = ZoneInfo("Europe/Berlin")
    dt_berlin = datetime.now(berlin_tz)
    print(f"ZoneInfo ('Europe/Berlin') success: {dt_berlin} (Offset: {dt_berlin.utcoffset()})")
except Exception as e:
    print(f"ZoneInfo ('Europe/Berlin') failed: {e}")
    print("-> Info: This is expected on Windows if the 'tzdata' package is not installed.")
    dt_berlin = None

# 2. Local System Time (Fallback)
dt_local = datetime.now()
print(f"Local System Time:                  {dt_local}")

# 3. UTC Time
dt_utc = datetime.utcnow()
print(f"UTC Time:                           {dt_utc}")

# 4. Resolve final string
resolved_dt = dt_berlin if dt_berlin is not None else dt_local
date_str = resolved_dt.strftime("%Y-%m-%d-%H-%M")
run_id = uuid.uuid4().hex[:8]
filename = f"Lime-{date_str}-{run_id}.json"

print(f"\nResolved Date String:               {date_str}")
print(f"Resolved Filename:                  {filename}")
