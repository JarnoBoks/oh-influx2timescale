
# Array of strings representing openHAB number items to be migrated to TimescaleDB.
#   everyChange persistence
#   Retention policy: 45 days
#   7d chunks
#   compression enabled

numbers45d_psql_retention_policy = "45 days"
numbers45d_influx_range = "-45d"

numbers_45d = [
    "my_number_item1",
    ]