# Units
from pint import UnitRegistry
ureg = UnitRegistry(case_sensitive=True)
Q_ = ureg.Quantity

# Import Inform for all modules
from inform import Inform, warn, fatal, error, display, comment, log, output, InformantFactory, debug
succeed = InformantFactory(message_color='green')
informer = Inform()

# default is the default in skillbridge
skillbridge_id: str | int | None = "default"

def set_skillbridge_id(value: str | int | None) -> None:
    global skillbridge_id
    skillbridge_id = value
