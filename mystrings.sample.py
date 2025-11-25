
# Array of strings representing openHAB string items to be migrated to TimescaleDB.
#   everyChange, everyDay persistence
#   7d retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no string items to migrate.

strings = [
    "my_string_item1",
    ]