
# Array of strings representing openHAB number items to be migrated to TimescaleDB.
#   everyChange persistence
#   No retention policy
#   7d chunks
#   compression enabled
#

# Array of strings representing openHAB number items to be migrated to TimescaleDB, fe.
# ["ItemName1", "ItemName2", ...]
# Use an empty array if there are no number items to migrate.
numbers = [
    ]