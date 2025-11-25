
# Array of strings representing openHAB contact items to be migrated to TimescaleDB.
#   everyUpdate persistence
#   No retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no contact items to migrate.

contacts = [
    "my_contact_item1",
    ]