
#
#   Numbers with retention policy of 45 days
#
#   everyChange persistence
#   Retention policy: 45 days
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no number items to migrate.

# The retention policy to be applied in TimescaleDB
numbers45d_psql_retention_policy = "45 days"

# The InfluxDB range to be used when querying data to migrate
numbers45d_influx_range = "-45d"

# Array of strings representing openHAB number items to be migrated to TimescaleDB with a set retention policy, fe.
# ["ItemName1", "ItemName2", ...]
numbers_45d = [
]