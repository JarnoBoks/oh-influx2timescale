
# Array of strings representing openHAB switch items to be migrated to TimescaleDB.
#   everyUpdate persistence
#   No retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no switch items to migrate.


switches = [
    "my_switch_item1",
    ]