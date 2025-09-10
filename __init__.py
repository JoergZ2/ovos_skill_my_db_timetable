import sys
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill
from ovos_bus_client.session import SessionManager
from ovos_date_parser import extract_datetime, nice_date
from deutsche_bahn_api.api_authentication import ApiAuthentication
from deutsche_bahn_api.station_helper import StationHelper
from deutsche_bahn_api.timetable_helper import TimetableHelper
from deutsche_bahn_api.train import Train
from deutsche_bahn_api.train_changes import TrainChanges
from datetime import datetime, timedelta
from time import sleep
from ovos_skill_my_db_timetable import train_types
#today = datetime.date.today()
station_helper = StationHelper()

DEFAULT_SETTINGS = {
    "__mycroft_skill_firstrun": "False",
    "client_id": "MyClientID",  # Example default setting
    "api_key": "MyApiKey"
}

class My_DB_Timetable_Skill(OVOSSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # be aware that below is executed after `initialize`
        self.override = True

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=True,
            network_before_load=False,
            gui_before_load=False,
            requires_internet=False,
            requires_network=False,
            requires_gui=False,
            no_internet_fallback=True,
            no_network_fallback=True,
            no_gui_fallback=True,
        )
    
    def initialize(self):
        #from template
        self.settings.merge(DEFAULT_SETTINGS, new_only=True)
        #self.settings_change_callback = self.on_settings_changed
        self.client_id = self.settings.get("client_id")
        self.api_key = self.settings.get("api_key")
        self.api = ApiAuthentication(self.client_id, self.api_key)
        self.register_entity_file('hour.entity')

    #Main functions
    def find_station(self,station, hour=None):
        """Find station by name, if multiple found, \
            a dialog is started to ask user to select one."""
        stations = []
        try:
            found_stations_by_name = station_helper.find_stations_by_name(station)
            for stat in found_stations_by_name:
                if stat.NAME.startswith(station):
                    stations.append(stat)
            if len(stations) == 0:
                self.speak_dialog('no_station', {"station": station})
                return
            if len(stations) == 1:
                return found_stations_by_name
            if len(stations) > 1:
                if "Hbf" not in station:
                    mainstation = self.ask_yesno('mainstation_yesno')
                    if mainstation == 'yes':
                        new_station = station + " Hbf"
                        found_mainstations = station_helper.find_stations_by_name(new_station)
                        if len(found_mainstations) == 1:
                            return found_mainstations
                        else:
                            station = self.station_recursion(station, found_mainstations)
                    elif mainstation == 'no':
                        station = self.station_recursion(station, found_stations_by_name)
                    else:
                        station = self.station_recursion(station, found_stations_by_name)
                else:
                    station = self.station_recursion(station, found_stations_by_name)
            return station
        except:
            LOG.info("Error: ", sys.exc_info()[0])
            LOG.info("No station found!" + " " + station)

    def get_connections(self, station, hour=None):
        """
        Get connections for a station at the current or at specific hour if given.
        """
        station = station[0]
        timetable_helper = TimetableHelper(station, self.api)
        if hour is not None:
            hour = int(hour)
            trains_in_this_hour = timetable_helper.get_timetable(hour) #List of train objects
        else:
            trains_in_this_hour = timetable_helper.get_timetable() #List of train objects
        LOG.debug("Connections: " + str(trains_in_this_hour))
        return trains_in_this_hour
            


    #Helper functions
    def station_recursion(self,station, stations):
        """
        Interview or query to narrow down the desired station.
        """
        self.speak_dialog('multiple_stations', {"station": station})
        i = 0
        station_names = []
        for stat in stations:
            if stat.NAME.startswith(station):
                station_names.append(stat.NAME)
        LOG.info("stations_matched are: " + str(station_names))
        for stat in station_names:
            self.speak_dialog('multiple_stations_loop2', {"station": station_names[i]})
            answer = self.ask_yesno('search_match', {"station": stat})
            if answer == 'yes':
                index = i
                LOG.info("2. level result: " + str(stations[index]))
                return [stations[index]]
            elif answer == 'no':
                i += 1
                continue
            else:
                i += 1
                continue

    def select_destination(self, stations):
        """
        Makes a list from a string which contains stations on the way to endpoint.
        """
        stations = stations.split("|")
        return(stations.pop())

    def pronouncable_list_of_connections(self,connections):
        """
        Creates a dictionary of pronouncable information \
            of each connection.
        """
        i = 0
        pronouncable_list = []
        single_connection = {}
        departure_order = []
        for train in connections:
            train_number = train.train_number
            train_type = train.train_type
            train_platform = train.platform
            train_departure = train.departure
            train_stations = train.stations
            if hasattr(train, 'arrival'):
                train_arrival = train.arrival
            else:
                train_arrival = "unknown"
            if hasattr(train, 'TrainChanges'):
                train_changes = train.TrainChanges
            else:
                train_changes = "no changes"
            #train_departure = speakable_time(train_departure)
            #train_stations = train.stations
            train_destination = self.select_destination(train.stations)
            single_connection = {"train_arrival": train_arrival, \
                                "train_changes": train_changes,\
                                "train_number": train_number, \
                                "train_type": train_type, \
                                "train_platform": train_platform, \
                                "train_departure": train_departure, \
                                "train_destination": train_destination,\
                                "train_stations": train_stations}
            pronouncable_list.append(single_connection)
        pronouncable_list.sort(key=lambda depart: depart['train_departure'])
        #for line in speakable_list:
        #print(line['train_type'] + ' Nummer ' + line['train_number'])
        LOG.debug("Speakable List of trains: " + str(pronouncable_list))
        return pronouncable_list
    
    def select_connections_by_endpoint(self, connections, endpoint):
        """
        Selects connections by endpoint if user specified one.
        """
        LOG.info("List before selection: " + str(connections))
        selected_connections = []
        for connection in connections:
            if endpoint in connection['train_destination'] or endpoint in connection['train_stations']:
                selected_connections.append(connection)
        LOG.info("List after selection: " + str(selected_connections))
        return selected_connections

    #Announcement functions
    def prepare_time(self,time_str):
        """
        Prepares a time string for announcement.
        """
        hour = time_str[6:8]
        minute = time_str[8:]
        return hour, minute
    
    def announce_of_departing_connections(self, pronouncable_list):
        """
        Announces the connections in a list.
        """
        self.speak_dialog('general_connection_announcement')
        for connection in pronouncable_list:
            hour, minute = self.prepare_time(connection['train_departure'])
            train_type = train_types.data.get(connection['train_type'], "Zug Art unbekannt")
            self.speak_dialog('train_departure', {"train_type": train_type, \
                                                "train_number": connection['train_number'], \
                                                "train_platform": connection['train_platform'], \
                                                "hour": hour, \
                                                "minute": minute, \
                                                "train_destination": connection['train_destination'], \
                                                "train_changes": connection['train_changes']})
            sleep(7)
            

    @intent_handler('timetable.intent')
    def handle_current_hour_timetable(self, message):
        """Function to fetch connections from a station at the current hour."""
        station = message.data.get('station')
        station = station.capitalize()
        utterance = message.data.get('utterance').lower()
        if "hauptbahnhof" in utterance:
            station = station + " Hbf"
        hour = message.data.get('hour', None)
        if hour is not None:
            LOG.debug("Hour from intent: " + str(hour))
            hour = str(hour[:2])
            LOG.debug("Hour from intent after replace: " + str(hour))
        station = self.find_station(station, hour) #find station from stations json file (offline)
        LOG.debug("Founded Station: " + str(station[0]))
        connections = self.get_connections(station, hour) #get timetable of current hour from selected station
        LOG.debug("Connections found: " + str(connections))
        pronouncable_list = self.pronouncable_list_of_connections(connections) #prepares timetable object to speakable list
        if len(pronouncable_list) == 0:
            self.speak_dialog('no_connections', {"station": station})
            return
        elif len(pronouncable_list) > 5:
            selection = self.ask_yesno('selection')
            if selection == 'yes':
                endpoint = self.get_response('set_destination')
                pronouncable_list = self.select_connections_by_endpoint(pronouncable_list, endpoint) #if user specified an endpoint, filter connections by it
        self.announce_of_departing_connections(pronouncable_list) #makes the announcement

