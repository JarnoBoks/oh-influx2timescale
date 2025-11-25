
# Array of strings representing openHAB number items to be migrated to TimescaleDB.
#
# This file can be used if there are 'combined' number items in the same influx Measurement.
# F.e. the measurement 'energies' has values for the items 'Feedin' and 'Retrieved'.
#   everyChange persistence
#   No retention policy
#   7d chunks
#   compression enabled
#
# Use an empty array if there are no number items to migrate.


numbers_combined = [
    ["influx_measurement_name", "openHAB_number_item1"],
    ["influx_measurement_name", "openHAB_number_item2"],
    ]