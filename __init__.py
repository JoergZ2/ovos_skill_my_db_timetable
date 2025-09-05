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
station_helper = StationHelper()
from datetime import datetime, timedelta
today = datetime.date.today()

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

    #Main functions
    def find_station(self,station, hour=None):
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
                LOG.info("One station found: " + stations[0].NAME)
                return found_stations_by_name
            if len(stations) > 1:
                mainstation = self.ask_yesno('mainstation_yesno')
                if mainstation == 'yes':
                    new_station = station * " Hbf"
                    found_stations_by_name = station_helper.find_stations_by_name(new_station)
                    if len(found_stations_by_name) == 1:
                        return found_stations_by_name
                    else:
                        self.station_recursion(station, stations)
                elif mainstation == 'no':
                    station = self.station_recursion(station, found_stations_by_name)
                else:
                    station = self.station_recursion(station, found_stations_by_name)
            return station
        except:
            LOG.info("Error: ", sys.exc_info()[0])
            LOG.info("No station found!" + " " + station)

    def get_connections(self, station, hour=None):
            station = station[0]
            timetable_helper = TimetableHelper(station, api)
            trains_in_this_hour = timetable_helper.get_timetable(hour) #List of train objects
            #speakable_list_of_trains(trains_in_this_hour)
            


    #Helper functions
    def station_recursion(self,station, stations):
        stations_matched = []
        for stat in stations:
            if stat.NAME.startswith(station):
                stations_matched.append(stat.NAME)
        for stat in stations_matched:
            self.speak_dialog()
            answer = self.ask_yesno('search_match', {"station": stat})
            if answer == 'yes':
                index = stat.index()
                return stations[index]
            else:
                continue

    #Dialog functions
            

    #intents
    @intent_handler('next_hour_timetable.intent')
    def handle_next_hour_timetable(self, message):
        station = message.data.get('station')
        hour = message.data.get('hour'), None
        station = self.find_station(station)
        connections = self.get_connections(station, hour)