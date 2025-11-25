
# Array of strings representing openHAB number items to be migrated to TimescaleDB.
#   everyChange persistence
#   No retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no number items to migrate.

numbers = [
    "my_number_item1",
    ]