from pade.layout.geometry import *
from pade.layout.pattern import Box
from pade.schematic import Terminal
from inform import warn
import numpy as np
import copy
from skillbridge import Workspace
from typing import List, Callable, Optional, ClassVar
from collections.abc import Iterable

Layer = Union[int, str]

class Path:
    """
    Path segment. Only straight wire in single layer
    """
    def __init__(self, layer, start, **kwargs) -> None:
        # Set layer, purpose pair
        self.layer = layer
        self.purpose = kwargs.get('purpose', 'drawing')

        if isinstance(start, Port):
            self.start = start.position
        else:
            self.start = Coordinate(start)
        self.stop = kwargs.get('stop')
        self.width = kwargs.get('width')
        self.begin_style = kwargs.get('begin_style', 'extend')
        self.end_style = kwargs.get('end_style', 'extend')
        self.net = kwargs.get('net')

        if 'dy' in kwargs:
            dy = kwargs['dy']
            self.stop = self.start + (0, dy)
        if 'dx' in kwargs:
            dx = kwargs['dx']
            self.stop = self.start + (dx, 0)

        # used only when begin or end style are set to custom
        # list( n_beginLeftDiagExt n_beginRightDiagExt n_beginRightHalfWidth n_endLeftDiagExt n_endRightDiagExt n_endRightHalfWidth)
        self.ext_value_list = kwargs.get('ext_value_list')


    def __str__(self):
        return f"Path in {self.layer} from {self.start} to {self.stop}"

    def __repr__(self) -> str:
        return self.__str__()

    def set_begin_style(self, style):
        self.begin_style = style

    def set_end_style(self, style):
        self.end_style = style

    def get_box(self):
        if self.start[0] == self.stop[0]:
            # In this case the path is vertical
            c1 = self.start - (self.width/2, 0)
            c2 = self.stop + (self.width/2, 0)
            return Box(origin=c1, opposite_corner=c2)
        else:
            # In this case the path is horizontal
            c1 = self.start - (0, self.width/2)
            c2 = self.stop + (0, self.width/2)
            return Box(origin=c1, opposite_corner=c2)
        
    @property
    def box(self) -> Box:
        return self.get_box()
    
    @property
    def center(self) -> Coordinate:
        return self.box.center

    def set_net(self, net_name):
        self.net = net_name

    def length(self):
        return Vector(self.start, self.stop).length()

class Route:
    """
    Route. May contain several path segments and vias
    """

    # Class-level callback (shared by all instances)
    get_layer_name: ClassVar[Optional[Callable[[Layer], str]]] = None
    get_via_names: Optional[Callable[[Layer, Layer, bool], List[str]]] = None
    get_via_name: Optional[Callable[[Layer, Layer, bool], str]] = None


    # Assign as staticmethod to prevent binding to self
    get_layer_name = staticmethod(get_layer_name)
    get_via_names = staticmethod(get_via_names)
    get_via_name = staticmethod(get_via_name)

    def __init__(self, start, stop, how, path_len_list=[], **kwargs) -> None:
        self.path_list = []
        self.via_list = []
        self.port_list = []
        self.width = None
        self.layer = None
        self.net = kwargs.get('net', None)
        # self.do_chop = kwargs.get('chop', False)
        # self.chop = None # Center coordinate of chop
        self.offset = kwargs.get('offset', 0)
        self.offset_end = kwargs.get('offset_end', 0)
        self.start_port = None
        self.end_port = None
        self.tech_file = kwargs.get('tech_file')
        self.purpose = kwargs.get('purpose', 'drawing')
        self.ncvias = kwargs.get('ncvias') # Corner vias
        self.cvia_rows = kwargs.get('cvia_rows') # Corner vias direction
        self.cvia_cols = kwargs.get('cvia_cols') # Corner vias direction
        if isinstance(start, Port):
            # If port, use center
            self.start = start.box.center
            self.start_port = start
            # Use start port box width(height) as routing width
            self.width = min(start.box.w, start.box.h)
            self.layer = start.layer
        elif isinstance(start, Path):
            self.start = start.get_box().center
            self.layer = start.layer
            self.width = min(start.get_box().w, start.get_box().h)
        elif isinstance(start, Box):
            self.start = start.center
        elif isinstance(start, Route):
            self.start = start.path_list[0].get_box().center
        else:
            self.start = Coordinate(start)

        if isinstance(stop, Port):
            # If port, use center
            self.stop = stop.box.center
            self.end_port = stop
            if self.width is None or self.layer is None:
                # Use stop port box width(height) as routing width
                self.width = min(stop.box.w, stop.box.h)
                self.layer = stop.layer
        elif isinstance(stop, Path):
            self.stop = stop.get_box().center
        elif isinstance(stop, Route):
            self.stop = stop.path_list[0].get_box().center
        elif isinstance(stop, Box):
            self.stop = stop.center
        else:
            self.stop = Coordinate(stop)

        # Possibility for overwriting width and layer:
        self.width = kwargs.get('width', self.width)
        self.layer = kwargs.get('layer', self.layer)

        self.validate_and_adjust_layer_names()

        if self.width is None or self.layer is None:
            raise ValueError('Route width and layer must be specified if start is not a Port')

        if how == '|-':
            self.route_vh()
        elif how == '-|':
            self.route_hv()
        elif how == '-':
            self.route_h()
        elif how == '|':
            self.route_v()
        elif how == '-|-':
            self.path_len_list = path_len_list
            self.route_custom_h()
        elif how == '|-|':
            self.path_len_list = path_len_list
            self.route_custom_v()
        else:
            warn('Route method not recognized')

        self.handle_path_style(**kwargs)

        # Add vias
        # TODO: Do this automatically. Currently must be done manually
        # Requires:
        # - Find names of required vias, should look in the tech file
        # - determine number of rows and cols for vias
        # if not self.start_port is None and self.tech_file is not None:
        #     if self.layer != self.start_port.layer:
        #         via_def_name = Via.find_via_def_name_from_layer_name(self.tech_file, self.start_port.layer, self.layer)

        # vias = kwargs.get('vias', [])
        # start_vias = kwargs.get('start_vias', vias)
        # end_vias = kwargs.get('end_vias', vias)

        # for via_name in start_vias:
        #     if self.start_port is None:
        #         raise ValueError('Can only add vias if start is a port')
        #     via = Via(via_name, box=self.start_port.box)
        #     self._add_via(via)

        # for via_name in end_vias:
        #     if self.end_port is None:
        #         raise ValueError('Can only add vias if end is a port')
        #     via = Via(via_name, box=self.end_port.box)
        #     self._add_via(via)

    @staticmethod
    def is_iterable_but_not_string(obj):
        '''
        Checks if the object is iterable and not a string.
        '''
        if isinstance(obj, (str, bytes)):
            return False
        try:
            iter(obj)
            return True
        except TypeError:
            return False


    def validate_and_adjust_layer_names(self):
        '''
        Validates the provided layer names and adjusts them if that is supported by the provided callback function. That is, it should be possible to provide aliases for the layers as long as the callback supports them and returns the proper layer names.
        '''
        if type(self).get_layer_name is not None:
            if type(self).is_iterable_but_not_string(self.layer):
                for i, layer in enumerate(self.layer):
                    self.layer[i] = type(self).get_layer_name(layer)
            else:
                self.layer = type(self).get_layer_name(self.layer)

    def __str__(self) -> str:
        return f"Route with {len(self.path_list)} Paths"

    def __repr__(self) -> str:
        return self.__str__()

    def __getitem__(self, key):
        return self.path_list[key]

    @property
    def start(self) -> Coordinate:
        return self._start
    
    @start.setter   #property-name.setter decorator
    def start(self, value):
        self._start = Coordinate(value)

    # begin = start
    # beginning = start

    @property
    def stop(self) -> Coordinate:
        return self._stop
    
    @stop.setter   #property-name.setter decorator
    def stop(self, value):
        self._stop = Coordinate(value)

    # end = stop
        
    @property
    def beginning(self) -> Coordinate:
        return self.path_list[0].start
    
    @property
    def end(self) -> Coordinate:
        return self.path_list[-1].stop
    
    # def end(self):
    #     return self.path_list[-1].stop

    def add_path(self, path):
        '''
        Return the path for later use in case it is added in a one-liner like:
        p = self.add_path(Path(self.get_layer(0), c0, dx=dx, width=self.width, purpose=self.purpose))
        '''
        self.path_list.append(path)
        return path

    def add_via_start(self, via_name_list: List[str], n_rows=1, n_cols=2, offset=[0, 0], **via_attr):
        '''
        Either:
        1. Provide a list of via names.
        2. Provide a single Layer.
        3. Provide 2 layers.
        '''
        p = self.path_list[0]
        center = p.start

        layer = via_attr.pop('layer', via_attr.pop('l', None))
        layer0 = via_attr.pop('layer0', via_attr.pop('l0', None))
        layer1 = via_attr.pop('layer1', via_attr.pop('l1', None))

        if (via_name_list is None) and (type(self).get_via_names is not None):
            if (layer is not None):
                via_name_list = type(self).get_via_names(p.layer, layer, True)
            elif (layer0 is not None)  and (layer1 is not None):
                via_name_list = type(self).get_via_names(layer0, layer1, True)

        for via_name in via_name_list:
            via = Via(via_name, center=center, n_rows=n_rows, n_cols=n_cols, offset=offset, via_attr=via_attr)
            self._add_via(via)

    def add_via_end(self, via_name_list: List[str], n_rows=1, n_cols=2, offset=[0, 0], **via_attr):
        '''
        Either:
        1. Provide a list of via names.
        2. Provide a single Layer.
        3. Provide 2 layers.
        '''
        p = self.path_list[-1]
        center = p.stop

        layer = via_attr.pop('layer', via_attr.pop('l', None))
        layer0 = via_attr.pop('layer0', via_attr.pop('l0', None))
        layer1 = via_attr.pop('layer1', via_attr.pop('l1', None))

        if (via_name_list is None) and (type(self).get_via_names is not None):
            if (layer is not None):
                via_name_list = type(self).get_via_names(p.layer, layer, True)
            elif (layer0 is not None)  and (layer1 is not None):
                via_name_list = type(self).get_via_names(layer0, layer1, True)

        for via_name in via_name_list:
            via = Via(via_name, center=center, n_rows=n_rows, n_cols=n_cols, offset=offset, via_attr=via_attr)
            self._add_via(via)

    add_via_begin = add_via_start
    add_via_stop = add_via_end

    def add_via_start_to_layer(self, layer: Layer, n_rows=1, n_cols=2, offset=[0, 0], **via_attr):
        p = self.path_list[0]

        if type(self).get_via_names is not None:
            via_names = type(self).get_via_names(p.layer, layer, True)
        else:
            raise NotImplemented()

        self.add_via_start(via_names, n_rows=n_rows, n_cols=n_cols, offset=offset, **via_attr)

    def add_via_end_to_layer(self, layer: Layer, n_rows=1, n_cols=2, offset=[0, 0], **via_attr):
        p = self.path_list[-1]

        if type(self).get_via_names is not None:
            via_names = type(self).get_via_names(p.layer, layer, True)
        else:
            raise NotImplemented()

        self.add_via_end(via_names, n_rows=n_rows, n_cols=n_cols, offset=offset, **via_attr)

    add_via_begin_to_layer = add_via_start_to_layer
    add_via_stop_to_layer = add_via_end_to_layer

    def _add_via(self, via):
        self.via_list.append(via)

    # def add_port_start(self, name):
    #     p = self.path_list[0]
    #     center = p.start

    #     box = p.get_box()
    #     w = min(box.w, box.h)

    #     # TODO: Place the port inside the Route in case of truncated edge. Need to consider direction.
    #     # c0.translate(dx=w/2)

    #     port_box = Box(center=center, w=w, h=w)
    #     port = Port(name, self.layer, port_box)
    #     self._add_port(port)

    # def add_port_end(self, name):
    #     p = self.path_list[-1]
    #     center = p.stop

    #     box = p.get_box()
    #     w = min(box.w, box.h)

    #     # TODO: Place the port inside the Route in case of truncated edge. Need to consider direction.
    #     # c0.translate(dx=w/2)

    #     port_box = Box(center=center, w=w, h=w)
    #     port = Port(name, self.layer, port_box)
    #     self._add_port(port)

    # add_port_begin = add_port_start
    # add_port_stop = add_port_end

    # def _add_port(self, port):
    #     self.port_list.append(port)

    def get_layer(self, index=0):
        '''
        self.layer can be a list with a number of layers that is less than the number of segments / paths as the modulo of the index is taken in this method. This makes it possible to loop around the list, allowing for example only 2 layers to be provided to the list while having a Route consisting of several segments / Paths, alternating between the layers. This is perfect for route_custom_h and route_custom_v which uses route_alternating.
        '''
        if isinstance(self.layer, str):
            return self.layer
        try:
            return self.layer[index % len(self.layer)]
        except:
            return self.layer

    def add_corner_via(self, pos, orient, layer0=None, layer1=None):
        try:
            if self.ncvias is None:
                nrows = 2 if orient == 'v' else 1
                ncols = 2 if orient == 'h' else 1
            else:
                nrows = ncols = self.ncvias
            if not self.cvia_cols is None:
                ncols = self.cvia_cols
            if not self.cvia_rows is None:
                nrows = self.cvia_rows

            layer_name0 = self.layer[0] if layer0 is None else layer0
            layer_name1 = self.layer[1] if layer1 is None else layer1

            # Validates layers and provides all the correct via names in between layer0 and layer1.
            if type(self).get_via_names is not None:
                via_names = type(self).get_via_names(layer_name0, layer_name1, True)

            # Supports only a single via
            # TODO: Make this support layers that are not necessarily next to each other.
            else:
                l0 = int(layer_name0[-1])
                l1 = int(layer_name1[-1])
                m1 = np.max((l0, l1))
                m0 = np.min((l0, l1))
                via_names = [f'M{m1}_M{m0}']

            for via_name in via_names:
                via = Via(via_name, center=pos, n_rows=nrows, n_cols=ncols)
                self._add_via(via)
        except:
            return

    def route_vh(self):
        """
        Route vertically, then horisontally
        """
        # First handle offset
        r_start = self.start
        r_stop = self.stop
        if self.offset != 0:
            if np.abs(self.offset) > 1.0:
                # As this route starts vertically, assume offset is horisontally
                p0 = Path(self.get_layer(1), self.start, dx=self.offset, width=self.width, purpose=self.purpose)
                self.add_path(p0)
                # Update r_start
                r_start += (self.offset, 0)
                # Add corner via
                self.add_corner_via(p0.stop, 'v')
            else:
                # As this route starts vertically, assume offset is horisontally
                p0 = Path(self.get_layer(0), self.start, dx=self.offset, width=self.width, purpose=self.purpose)
                self.add_path(p0)
                # Update r_start
                r_start += (self.offset, 0)

        p_end = None
        if self.offset_end != 0:
            # As this route ends horisontally, assume end offset is vertical
            p_end = Path(self.get_layer(0), r_stop+(0, self.offset_end), dy=-self.offset_end, width=self.width, purpose=self.purpose)
            # Update r_stop
            r_stop += (0, self.offset_end)
            # Add corner via
            self.add_corner_via(p_end.start, 'h')

        vector = r_stop - r_start
        dy=vector[1]
        dx=vector[0]
        p1 = Path(self.get_layer(0), r_start, dy=dy, width=self.width, purpose=self.purpose)
        if not dy == 0:
            self.add_path(p1)
            # Add corner via
            self.add_corner_via(p1.stop, 'v')
        if not dx == 0:
            p2 = Path(self.get_layer(1), p1.stop, dx=dx, width=self.width, purpose=self.purpose)
            self.add_path(p2)
        if not p_end is None:
            self.add_path(p_end)

    def route_hv(self):
        """
        Route horisontally, then vertically
        """
        r_start = self.start
        r_stop = self.stop

        # First handle offset
        if self.offset != 0:
            if np.abs(self.offset) > 1.0:
                # As this route starts horisontally, assume self.offset is vertically
                p0 = Path(self.get_layer(1), r_start, dy=self.offset, width=self.width, purpose=self.purpose)
                self.add_path(p0)
                # Update r_start
                r_start += (0, self.offset)
                # Add corner via
                self.add_corner_via(p0.stop, 'v')
            else:
                # As this route starts horisontally, assume self.offset is vertically
                p0 = Path(self.get_layer(0), r_start, dy=self.offset, width=self.width, purpose=self.purpose)
                self.add_path(p0)
                # Update r_start
                r_start += (0, self.offset)

        p_end = None
        if self.offset_end != 0:
            # As this route ends vertically, assume end offset is horisontal
            p_end = Path(self.get_layer(0), r_stop+(self.offset_end,0), dx=-self.offset_end, width=self.width, purpose=self.purpose)
            # Update r_stop
            r_stop += (self.offset_end, 0)
            # Add corner via
            self.add_corner_via(p_end.start, 'h')

        vector = r_stop - r_start
        dy=vector[1]
        dx=vector[0]
        # dx = dx  - self.width/2 if dx > 0 else dx + self.width/2
        p1 = Path(self.get_layer(0), r_start, dx=dx, width=self.width, purpose=self.purpose)
        if not dx == 0:
            self.add_path(p1)
            # Add corner via
            self.add_corner_via(p1.stop, 'v')
        if not dy == 0:
            p2 = Path(self.get_layer(1), p1.stop, dy=dy, width=self.width, purpose=self.purpose)
            self.add_path(p2)

        if not p_end is None:
            self.add_path(p_end)

    def route_h(self):
        """
        Horizontal route.
        """
        r_start = self.start
        # First handle offset
        if self.offset != 0:
            # As this route starts horisontally, assume self.offset is vertically
            p0 = Path(self.get_layer(0), r_start, dy=self.offset, width=self.width, purpose=self.purpose)
            self.add_path(p0)
            # Update r_start
            r_start += (0, self.offset)

        r_stop = Coordinate((self.stop[0], r_start[1]))
        self.stop = r_stop

        dx = self.stop[0] - r_start[0]
        if dx != 0:
            self.add_path(Path(self.get_layer(0), r_start, dx=dx, width=self.width, purpose=self.purpose))

    def route_v(self):
        """
        Vertical route.
        """
        r_start = self.start
        if self.offset != 0:
            # As this route starts vertically, assume offset is horisontally
            p0 = Path(self.get_layer(0), self.start, dx=self.offset, width=self.width, purpose=self.purpose)
            self.add_path(p0)
        # Update r_start
        r_start += (self.offset, 0)

        r_stop = Coordinate((r_start[0], self.stop[1]))
        self.stop = r_stop

        dy = self.stop[1] - r_start[1]
        if dy != 0:
            self.add_path(Path(self.get_layer(0), r_start, dy=dy, width=self.width, purpose=self.purpose))

    def route_custom_h(self):
        """
        Custom route, start horisontally
        """
        self.route_alternating(True)

    def route_custom_v(self):
        """
        Custom route, start vertically
        """
        self.route_alternating(False)

    def route_alternating(self, go_horizontal):
        c0 = self.start
        for i, path_len in enumerate(self.path_len_list):
            
            layer1 = self.get_layer(i)

            if go_horizontal:
                p = self.add_path(Path(layer1, c0, dx=path_len, width=self.width, purpose=self.purpose))
                c0 += (path_len, 0)
            else:
                p = self.add_path(Path(layer1, c0, dy=path_len, width=self.width, purpose=self.purpose))
                c0 += (0, path_len)
            go_horizontal = not go_horizontal

            if i != 0:
                layer0 = self.get_layer(i-1)

                if layer0 != layer1:
                    dir = 'v' if go_horizontal else 'h'
                    self.add_corner_via(p.start, dir, layer0, layer1)

        layer0 = layer1
        layer1 = self.get_layer(i+1)

        # Finally, go to end
        if go_horizontal:
            dx = self.stop[0] - c0[0]
            if dx != 0:
                p = self.add_path(Path(layer1, c0, dx=dx, width=self.width, purpose=self.purpose))
        else:
            dy = self.stop[1] - c0[1]
            if dy != 0:
                p = self.add_path(Path(layer1, c0, dy=dy, width=self.width, purpose=self.purpose))

        if layer0 != layer1:
            dir = 'v' if go_horizontal else 'h'
            self.add_corner_via(p.start, dir, layer0, layer1)

        # The real stop of the route will be the new stop of self. Not the given stop Coordinate.
        self.stop = p.stop

    def handle_path_style(self, **kwargs):
        # Add begin/end styles
        if 'begin_style' in kwargs:
            self.path_list[0].set_begin_style(kwargs['begin_style'])
        if 'end_style' in kwargs:
            self.path_list[-1].set_end_style(kwargs['end_style'])

    def length(self):
        sum = 0
        for p in self.path_list:
            sum += p.length()
        return sum
    
    def get_boxes(self):
        return [p.box for p in self.path_list]
    
class Via:
    """
    Via. May have multiple rows and columns of vias
    """

    # Class-level callback (shared by all instances)
    adjust_callback: ClassVar[Optional[Callable[['Via'], bool]]] = None
    get_via_name: Optional[Callable[[Layer, Layer, bool], str]] = None

    # Assign as staticmethod to prevent binding to self
    get_via_name = staticmethod(get_via_name)

    # Index of via spacing rules in tech file parameter list
    # Might be tech-dependent?
    via_width_rule_index = 1
    via2via_space_rule_index = 5
    via2bound_space_rule_index = 6

    @staticmethod
    def validate_via_name(via_name):
        pass

    @staticmethod
    def find_via_def_name_from_layer_name(tech_file, layer1_name, layer2_name):
        # if type(self).get_via_names is not None:
        #     via_name = type(self).get_via_names(layer1_name, layer2_name, True)
        #     if via_name in tech_file.via_defs: return via_name
        # else:
        for via_def in tech_file.via_defs:
            if via_def.layer1.name == layer1_name and via_def.layer2.name == layer2_name:
                return via_def.name
        # return False

    def __init__(self, via_def_name, **kwargs) -> None:
        self.via_def_name = via_def_name
        self.n_rows = kwargs.get('n_rows')
        self.n_cols = kwargs.get('n_cols')

        self.box = kwargs.get('box')
        port = kwargs.get('port')
        if port is not None:
            self.box = port.box

        self.center = kwargs.get('center', None)

        self.via_attr = kwargs.get('via_attr', {})

        offset = kwargs.get('offset', [0, 0])
        if self.center is not None:
            self.center += offset

    def __str__(self) -> str:
        return f"Via {self.via_def_name} with {self.n_rows} rows and {self.n_cols} columns"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def center(self) -> Coordinate:
        return self._center
    
    @center.setter   #property-name.setter decorator
    def center(self, value):
        if (isinstance(value, list)):
            self._center = Coordinate(value)
        elif (isinstance(value, Box)):
            self._center = value.center
        elif (isinstance(value, Port)):
            self._center = value.center
        elif (isinstance(value, Coordinate)):
            self._center = value
        elif value is None:
            if self.box is not None:
                self.center = self.box.center
            else:
                self.center = value
        else:
            self._center = value
            # raise ValueError(f'Invalid input value: {value}')

    @staticmethod
    def parse_tech_file_rules(tech_file_param_list):
        via_width = tech_file_param_list[Via.via_width_rule_index]
        via2via_space = tech_file_param_list[Via.via2via_space_rule_index]
        via2bound_space = tech_file_param_list[Via.via2bound_space_rule_index][0]

        return via_width, via2via_space, via2bound_space

    def set_via_param_from_tech_file_rules(self, tech_file_param_list):
        via_width, via2via_space, via2bound_space = Via.parse_tech_file_rules(tech_file_param_list)

        # Calculate required number of cols and rows based on box
        self.via_width = via_width
        # via2via space is a list. Assume rules for W and H are equal and select first entry
        self.via2via_space = via2via_space
        # Overwrite if given as viaAttr:
        if 'cutSpacing' in self.via_attr:
            self.via2via_space = self.via_attr['cutSpacing']
        # via2bound space is a list. Assume rules for W and H are equal and select first entry
        self.via2bound_space = via2bound_space

    def get_via_params(self, tech_file_param_list=None):
        via_param_list = []
        if (tech_file_param_list is not None):
            self.set_via_param_from_tech_file_rules(tech_file_param_list)
            if self.box is not None and self.n_rows is None and self.n_cols is None:
                self.determine_rows_and_cols()
                if type(self).adjust_callback is not None: # Use external / custom function to adjust vias.
                    if type(self).adjust_callback(self):
                        self.determine_rows_and_cols()
            else:
                if type(self).adjust_callback is not None: # Use external / custom function to adjust vias.
                    type(self).adjust_callback(self)

        via_param_list = [
            ["cutRows", self.n_rows],
            ["cutColumns", self.n_cols],
            ]
        
        if (hasattr(self, 'via2via_space')):
            via_param_list.append(["cutSpacing", self.via2via_space])

        for key, value in self.via_attr.items():
            via_param_list.append([key, value])

        return via_param_list
        
    def determine_rows_and_cols(self):
        via_unit_width = self.via_width + self.via2via_space[0]
        self.n_cols = int((self.box.w - self.via_width - 2*self.via2bound_space) / via_unit_width) + 1

        self.n_rows = int((self.box.h - self.via_width - 2*self.via2bound_space) / via_unit_width) + 1

class Port:
    """
    Port on Layout. Generates a figure(rect), net, terminal and a pin
    """
    def __init__(self, name, *args, **kwargs) -> None:
        if isinstance(name, Terminal):
            self.name = name.name
        else:
            self.name = name

        if len(args) == 1 and isinstance(args[0], Route):
            route = args[0]
            self._init_from_route(route, **kwargs)
        elif len(args) == 1 and isinstance(args[0], Path):
            path = args[0]
            self.layer = path.layer
            self.box = path.get_box()
            self.position = self.box.center
        elif len(args) == 1 and isinstance(args[0], Port):
            port = args[0]
            self.layer = port.layer
            self.box = port.box
            self.position = self.box.center
        elif len(args) == 2 and isinstance(args[-1], Box):
            self.layer = args[0]
            self.box = copy.deepcopy(args[-1])
            self.position = self.box.center
        elif len(args) == 2 and not isinstance(args[-1], Box):
            self.layer = args[0]
            self.position = args[1]
            box_width = kwargs.get('box_width', 0.2)
            box = kwargs.get('box', None)
            self.box = copy.deepcopy(box) if box is not None else Box(diagonal=(box_width, box_width))
        elif len(args) == 3:
            # Assume layer, position and box
            self.layer = args[0]
            self.position = args[1]
            self.box = args[2]
        else:
            raise ValueError('Invalid input arguments')
        
        self.box.set_origin(center=self.position)

    def _init_from_route(self, route, **kwargs):
        self.layer = route.layer

        start = kwargs.get('start') or kwargs.get('begin', False)
        stop = kwargs.get('stop') or kwargs.get('end', False)
        edge = kwargs.get('edge', False) # If True: place the port on one of the ends of a path (start, stop), else, cover the whole path (start, stop).

        if stop and not start:
            path = route.path_list[-1]
            if isinstance(self.layer, Iterable) and not isinstance(self.layer, (str, bytes, bytearray)): self.layer = self.layer[-1]

            if edge:
                c0 = route.stop
                direction = Vector(path.start, path.stop).normalize()
        else:
            path = route.path_list[0]
            if isinstance(self.layer, Iterable) and not isinstance(self.layer, (str, bytes, bytearray)): self.layer = self.layer[0]

            if edge:
                c0 = route.start
                direction = Vector(path.stop, path.start).normalize()

        if edge:
            box = path.get_box()
            w = min(box.w, box.h)

            if (start and stop) or (not start and not stop):
                raise RuntimeError(f'Which side should the port be added to?: start={start} and stop={stop}')
            elif (stop and (path.end_style == 'extend')) or (start and (path.begin_style == 'extend')):
                center = c0
            elif (stop and (path.end_style == 'truncate')) or (start and (path.begin_style == 'truncate')):
                center = c0 - direction*(w/2)
            else:
                raise ValueError(f'Unknown path end style: {path.end_style}')

            self.box = Box(center=center, w=w, h=w)
        else:
            self.box = path.get_box()
        
        
        self.position = self.box.center
        self.box.set_origin(center=self.position)

    @property
    def position(self) -> Coordinate:
        return self._position
    
    @position.setter   #property-name.setter decorator
    def position(self, value):
        self._position = Coordinate(value)

    def __str__(self) -> str:
        return f"Port {self.name} in {self.layer} at {self.position}"

    def __repr__(self) -> str:
        return self.__str__()

    def __sub__(self, other):
        if isinstance(other, Port):
            return Vector(other.position, self.position)
        else:
            raise NotImplementedError()

    @property
    def x(self) -> float:
        return self.box.center.x
    
    @property
    def y(self) -> float:
        return self.box.center.y
    
    @property
    def center(self) -> Coordinate:
        return self.box.center

    @center.setter   #property-name.setter decorator
    def center(self, value):
        self.box.center = value

    # def center(self) -> Coordinate:
    #     return self.box.center

    def bct(self, *args, dx=None, dy=None):
        '''
        Port Box Center Translate -> Port BCT
        This method will replace having to write out all of the below where D is the Port of a Cell:
        self.cell.D.box.center.translate(dx=SD_OFFSET/2)

        Allowing the following to be written:
        self.cell.D.bct(dx=SD_OFFSET/2)
        '''
        return self.box.center.translate(*args, dx=dx, dy=dy)
    
    ct = bct # Center Translate

    def translate(self, translation):
        self.position += translation
