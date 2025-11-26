
# Array of strings representing openHAB string items to be migrated to TimescaleDB.
#   everyChange, everyDay persistence
#   7d retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no string items to migrate.

# The retention policy to be applied in TimescaleDB
string_retention_policy = "7 days"

# The InfluxDB range to be used when querying data to migrate
strings_influx_range = "-10d"


# Array of strings representing openHAB string items to be migrated to TimescaleDB, fe.
# ["ItemName1", "ItemName2", ...]
# Use an empty array if there are no string items to migrate.
strings = [
    ]