import functools
import logging
import re
import io
import serial
import string
import time
import asyncio
from functools import wraps
from threading import RLock

_LOGGER = logging.getLogger(__name__)
#logging.basicConfig(format='%(asctime)s;%(levelname)s:%(message)s', level=logging.DEBUG)

'''
#Z0xPWRppp,SRCs,VOL-yy<CR>
'''
CONCERTO_PATTERN = re.compile('Z0(?P<zone>\d)'
                     'PWR(?P<power>ON|OFF),'
                     'SRC(?P<source>\d),'
                     'VOL(?P<volume>-\d\d|MT)')


'''
#Z0xPWRppp,SRCs,GRPt,VOL-yy<CR>
'''
SIMPLESE_PATTERN = re.compile('Z0(?P<zone>\d)'
                     'PWR(?P<power>ON|OFF),'
                     'SRC(?P<source>\d),'
                     'GRP(?P<group>0|1),'
                     'VOL(?P<volume>-\d\d|MT|XM)')


'''
Z02STR+"TUNER"
'''
SOURCE_PATTERN = re.compile('Z0(?P<zone>\d)'
                     'STR\+\"(?P<name>.*)\"')


EOL = b'\r'
TIMEOUT_OP       = 0.2   # Number of seconds before serial operation timeout
TIMEOUT_RESPONSE = 2.5   # Number of seconds before command response timeout
VOLUME_DEFAULT  = -40    # Value used when zone is muted or otherwise unable to get volume integer

class ZoneStatus(object):
    def __init__(self
                 ,zone: int
                 ,power: str
                 ,source: int
                 ,volume: float  # -78 -> 0
                 ):
        self.zone = zone
        if 'ON' in power:
           self.power = bool(1)
        else:
           self.power = bool(0)
        self.source = str(source)
        self.sourcename = ''
#        self.treble = treble
#        self.bass = bass
        if 'MT' in volume:
           self.mute = bool(1)
           self.volume = VOLUME_DEFAULT
        else:
           self.mute = bool(0)
           self.volume = int(volume) 
        self.treble = 0 
        self.bass = 0

    @classmethod
    def from_string(cls, string: bytes):
        if not string:
            return None

        match = _parse_response(string)
   
        if not match:
            return None

        try:
           rtn = ZoneStatus(*[str(m) for m in match.groups()])
        except:
           rtn = None
        return rtn

class Nuvo(object):
    """
    Nuvo amplifier interface
    """

    def zone_status(self, zone: int):
        """
        Get the structure representing the status of the zone
        :param zone: zone 1.12
        :return: status of the zone or None
        """
        raise NotImplemented()

    def set_power(self, zone: int, power: bool):
        """
        Turn zone on or off
        :param zone: zone 1.12        
        :param power: True to turn on, False to turn off
        """
        raise NotImplemented()

    def set_mute(self, zone: int, mute: bool):
        """
        Mute zone on or off
        :param zone: zone 1.12        
        :param mute: True to mute, False to unmute
        """
        raise NotImplemented()

    def set_volume(self, zone: int, volume: float):
        """
        Set volume for zone
        :param zone: zone 1.12        
        :param volume: float from -78 to 0 inclusive
        """
        raise NotImplemented()

    def set_treble(self, zone: int, treble: float):
        """
        Set treble for zone
        :param zone: zone 1.12        
        :param treble: float from -12 to 12 inclusive
        """
        raise NotImplemented()

    def set_bass(self, zone: int, bass: int):
        """
        Set bass for zone
        :param zone: zone 1.12        
        :param bass: float from -12 to 12 inclusive 
        """
        raise NotImplemented()

    def set_source(self, zone: int, source: int):
        """
        Set source for zone
        :param zone: zone 1.6        
        :param source: integer from 1 to 6 inclusive
        """
        raise NotImplemented()

    def restore_zone(self, status: ZoneStatus):
        """
        Restores zone to it's previous state
        :param status: zone state to restore
        """
        raise NotImplemented()


# Helpers

def _is_int(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def _parse_response(string: bytes):
   """
   :param request: request that is sent to the nuvo
   :return: regular expression return match(s) 
   """
   match = re.search(CONCERTO_PATTERN, string)
   if match:
      _LOGGER.debug('CONCERTO_PATTERN - Match')
      return match

   if not match:
      match = re.search(SIMPLESE_PATTERN, string)
      if match:
         _LOGGER.debug('SIMPLESE_PATTERN - Match')
         return match

   if not match:
      match = re.search(SOURCE_PATTERN, string)
      if match:
         _LOGGER.debug('SOURCE_PATTERN - Match')
         return match

   if (string == '#Busy'):
       _LOGGER.debug('BUSY RESPONSE - TRY AGAIN')
   return None

   if not match:
       _LOGGER.debug('NO MATCH - %s' , string)
   return None

def _format_zone_status_request(zone: int) -> str:
    return 'Z{:0=2}STATUS'.format(zone)

def _format_set_power(zone: int, power: bool) -> str:
    zone = int(zone)
    if (power):
       return 'Z{:0=2}ON'.format(zone) 
    else:
       return 'Z{:0=2}OFF'.format(zone)

def _format_set_mute(zone: int, mute: bool) -> str:
    if (mute):
       return 'Z{:0=2}MTON'.format(int(zone))
    else:
       return 'Z{:0=2}MTOFF'.format(int(zone))

def _format_set_volume(zone: int, volume: float) -> str:
    # If muted, status has no info on volume level
    if _is_int(volume):
       # Negative sign in volume parm produces erronous result
       volume = abs(volume)
       volume = round(volume,0)
    else:
       # set to default value
       volume = abs(VOLUME_DEFAULT) 

    return 'Z{:0=2}VOL{:0=2}'.format(int(zone),volume)

def _format_set_treble(zone: int, treble: int) -> bytes:
    treble = int(max(12, min(treble, -12)))
    return 'Z{:0=2}TREB{:0=2}'.format(int(zone),treble)

def _format_set_bass(zone: int, bass: int) -> bytes:
    bass = int(max(12, min(bass, -12)))
    return 'Z{:0=2}BASS{:0=2}'.format(int(zone),bass)

def _format_set_source(zone: int, source: int) -> str:
    source = int(max(1, min(int(source), 6)))
    return 'Z{:0=2}SRC{}'.format(int(zone),source)

def get_nuvo(port_url):
    """
    Return synchronous version of Nuvo interface
    :param port_url: serial port, i.e. '/dev/ttyUSB0,/dev/ttyS0'
    :return: synchronous implementation of Nuvo interface
    """

    lock = RLock()

    def synchronized(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper

    class NuvoSync(Nuvo):
        def __init__(self, port_url):
            _LOGGER.info('Attempting connection - "%s"', port_url)
            self._port = serial.serial_for_url(port_url, do_not_open=True)
            self._port.baudrate = 9600
            self._port.stopbits = serial.STOPBITS_ONE
            self._port.bytesize = serial.EIGHTBITS
            self._port.parity = serial.PARITY_NONE
            self._port.timeout = TIMEOUT_OP
            self._port.write_timeout = TIMEOUT_OP
            self._port.open()


        def _send_request(self, request):
            """
            :param request: request that is sent to the nuvo
            :return: bool if transmit success
            """
            #format and send output command
            lineout = "*" + request + "\r"
            _LOGGER.info('Sending "%s"', request)
            #Below line is not displayed properly in logger
            #_LOGGER.info('Sending "%s"', lineout)
            self._port.write(lineout.encode())
            self._port.flush() # it is buffering
            return True


        def _listen_maybewait(self, wait_for_response: bool):

            no_data = False
            receive_buffer = b''
            message = b''
            start_time = time.time()
            timeout = TIMEOUT_RESPONSE 

            # listen for response
            while (no_data == False):

               # Exit if timeout
               if( (time.time() - start_time) > timeout ):
                  _LOGGER.warning('Expected response from command but no response before timeout')
                  return None

               # fill buffer until we get term seperator 
               data = self._port.read(1)

               if data:
                  receive_buffer += data

                  if EOL in receive_buffer:
                     message, sep, receive_buffer = receive_buffer.partition(EOL)
                     _LOGGER.debug('Received: %s', message)
                     _parse_response(str(message))
                     return(str(message))
                  else:
                     _LOGGER.debug('Expecting response from command sent - Data received but no EOL yet :(')
               else:
                  _LOGGER.debug('Expecting response from command sent - No Data received')
                  if ( wait_for_response == False ): 
                     no_data = True
                  continue

            return None

        def _process_request(self, request: str):
            """
            :param request: request that is sent to the nuvo
            :return: ascii string returned by nuvo
            """

            # Process any messages that have already been received 
            self._listen_maybewait(False)

            # Send command to device
            self._send_request(request)

            # Process expected response
            rtn =  self._listen_maybewait(True)

            return rtn

        @synchronized
        def zone_status(self, zone: int):
            # Send command multiple times, since we need result back, and rarely response can be wrong type 
            for count in range(1,5):
               try:
                  rtn = ZoneStatus.from_string(self._process_request(_format_zone_status_request(zone)))
                  if rtn == None:
                     _LOGGER.debug('Zone Status Request - Response Invalid - Retry Count: %d' , count)
                     raise ValueError('Zone Status Request - Response Invalid')
                  else:
                     return rtn
                     break  # Successful execution; exit for loop
               except:
                  rtn = None
               #Wait 1 sec between retry attempt(s)
               time.sleep(1)
               continue  # end of for loop // retry
            return rtn

        @synchronized
        def set_power(self, zone: int, power: bool):
            self._process_request(_format_set_power(zone, power))

        @synchronized
        def set_mute(self, zone: int, mute: bool):
            self._process_request(_format_set_mute(zone, mute))

        @synchronized
        def set_volume(self, zone: int, volume: float):
            self._process_request(_format_set_volume(zone, volume))

        @synchronized
        def set_treble(self, zone: int, treble: float):
            self._process_request(_format_set_treble(zone, treble))

        @synchronized
        def set_bass(self, zone: int, bass: float):
            self._process_request(_format_set_bass(zone, bass))

        @synchronized
        def set_source(self, zone: int, source: int):
            self._process_request(_format_set_source(zone, source))

        @synchronized
        def restore_zone(self, status: ZoneStatus):
            self.set_power(status.zone, status.power)
            self.set_mute(status.zone, status.mute)
            self.set_volume(status.zone, status.volume)
            self.set_source(status.zone, status.source)
#            self.set_treble(status.zone, status.treble)
#            self.set_bass(status.zone, status.bass)

    return NuvoSync(port_url)


