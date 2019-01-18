import time
from pynuvo import get_nuvo

nuvo = get_nuvo('/dev/ttyS0')

# Valid zones are 1-8 for nuvo concerto amplifier
for x in range(1,8):
   zone_status = nuvo.zone_status(x)


zone_status = nuvo.zone_status(1)

# Print zone status
print('Zone Number = {}'.format(zone_status.zone))
print('Power is {}'.format('On' if zone_status.power else 'Off'))
print('Mute is {}'.format('On' if zone_status.mute else 'Off'))
print('Volume = {}'.format(zone_status.volume))
print('Source = {}'.format(zone_status.source))

# Turn on zone #1
nuvo.set_power(1, True)

# Set source 2 for zone #1
nuvo.set_source(1, 2)

# Mute zone #1
nuvo.set_mute(1,True)

# Set volume for zone #1
nuvo.set_volume(1, -45)

# Set source 1 for zone #4 
nuvo.set_source(4, 1)

# Turn off zone #1
nuvo.set_power(1, False)

time.sleep(2)

# Restore zone #1 to it's original state
nuvo.restore_zone(zone_status)

zone_status = nuvo.zone_status(1)

# Print zone status
print('Zone Number = {}'.format(zone_status.zone))
print('Power is {}'.format('On' if zone_status.power else 'Off'))
print('Mute is {}'.format('On' if zone_status.mute else 'Off'))
print('Volume = {}'.format(zone_status.volume))
print('Source = {}'.format(zone_status.source))

