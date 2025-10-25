import numpy as np
from typing import Iterable, Union

# TODO: Add support for DBU and units
class Coordinate:

    DBU = 0.001

    # Manual immutability
    __slots__ = ("_x", "_y")  # optional, but makes instances smaller and faster

    def __init__(self, *args, x=None, y=None):
        if x is not None and y is not None:
            _x, _y = float(x), float(y)
        elif len(args) == 2:
            _x, _y = float(args[0]), float(args[1])
        elif len(args) == 1:
            arg = args[0]
            if isinstance(arg, Coordinate) or (hasattr(arg, "x") and hasattr(arg, "y")):
                _x, _y = float(arg.x), float(arg.y)
            elif hasattr(arg, "__getitem__") and len(arg) == 2:
                _x, _y = float(arg[0]), float(arg[1])
            else:
                raise TypeError(f"Invalid coordinate initializer: {arg}")
        else:
            raise TypeError("Coordinate accepts (x, y), ((x, y)), [x, y], or another Coordinate")

        # Bypasses custom __setattr__
        object.__setattr__(self, "_x", _x)
        object.__setattr__(self, "_y", _y)

    @property
    def x(self) -> float:
        return self._x

    @property
    def y(self) -> float:
        return self._y
    
    # This prevents the attributes of the Coordinate from being changed after the Coordinate has been created (immutability guard)
    def __setattr__(self, name, value):
        raise AttributeError(f"{self.__class__.__name__} is immutable")

    def to_skill(self, decimals=0):
        return f"{round(self.x/Coordinate.DBU, decimals=decimals)*Coordinate.DBU}:{round(self.y/Coordinate.DBU, decimals=decimals)*Coordinate.DBU}"

    def to_list(self, decimals=0):
        return [np.round(self.x/Coordinate.DBU, decimals=decimals)*Coordinate.DBU, np.round(self.y/Coordinate.DBU, decimals=decimals)*Coordinate.DBU]

    def __iter__(self):
        return iter((self._x, self._y))

    def __len__(self):
        return 2

    def tuple(self):
        return (self.x, self.y)

    def __round__(self, ndigits=0):
        return self.__class__((round(self._x, ndigits), round(self._y, ndigits)))

    def __contains__(self, value):
        """Return True if value matches x or y component."""
        return value == self._x or value == self._y

    def __getitem__(self, item):
        if item == 0:
            return self.x
        elif item == 1:
            return self.y
        else:
            raise ValueError(f'{item} is an invalid index for Coordinate. The index must be 0 or 1.')

    def __add__(self, other: Union['Coordinate', tuple, list, float, int]):
        if isinstance(other, Coordinate):
            return self.__class__(self._x + other._x, self._y + other._y)
        elif hasattr(other, "__getitem__"):
            return self.__class__(self._x + other[0], self._y + other[1])
        elif hasattr(other, "x") and hasattr(other, "y"):
            return self.__class__(self._x + other.x, self._y + other.y)
        else:
            return self.__class__(self._x + other, self._y + other)

    def __sub__(self, other):
        if isinstance(other, Coordinate):
            return self.__class__(self._x - other._x, self._y - other._y)
        elif hasattr(other, "__getitem__"):
            return self.__class__(self._x - other[0], self._y - other[1])
        elif hasattr(other, "x") and hasattr(other, "y"):
            return self.__class__(self._x - other.x, self._y - other.y)
        else:
            return self.__class__(self._x - other, self._y - other)
        
    def __truediv__ (self, value: float):
        return self.__class__(self._x / value, self._y / value)

    def __mul__(self, scalar: float):
        return self.__class__(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __abs__(self) -> float:
        """Return the vector magnitude (Euclidean norm)."""
        return (self._x ** 2 + self._y ** 2) ** 0.5

    def mag(self) -> float:
        """Alias for abs(): vector magnitude."""
        return abs(self)

    def magnitude(self) -> float:
        """Alias for abs(): vector magnitude."""
        return abs(self)

    def __neg__(self):
        """Return a new Coordinate with both components negated."""
        return self.__class__(-self._x, -self._y)

    def __eq__(self, other):
        return isinstance(other, Coordinate) and self._x == other._x and self._y == other._y # polymorphic equality
        # return type(other) is type(self) and self._x == other._x and self._y == other._y # subclass awareness

    def __hash__(self):
        return hash((self._x, self._y))

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self._x}, {self._y})'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._x}, {self._y})'
    
    def __deepcopy__(self, memo):
        # Since immutable, just return self
        return self

    def translate(self, *args): # , dx=0.0, dy=0.0
        if len(args) == 2:
            dx, dy = float(args[0]), float(args[1])
        elif len(args) == 1:
            arg = args[0]
            if isinstance(arg, Coordinate):
                dx, dy = float(arg.x), float(arg.y)
            elif hasattr(arg, "__getitem__") and len(arg) == 2:
                dx, dy = float(arg[0]), float(arg[1])
            else:
                raise TypeError(f"Invalid argument: {arg}")
            
        return self.__class__(self.x + dx, self.y + dy)
    
    @classmethod
    def midpoint(cls, a, b):
        a = Coordinate(a)
        b = Coordinate(b)

        return cls.avg([a, b])
    
    @classmethod
    def avg(cls, coords: Iterable['Coordinate']):
        if not coords:
            raise ValueError("Cannot calculate average of empty coordinate list")
    
        coords = list(coords) # supports any iterable

        total = sum(coords[1:], coords[0])
        return cls(total.x / len(coords), total.y / len(coords))

class Vector:
    """
    Vector class
    Stores only a np array
    """
    def __init__(self, *args) -> None:
        if len(args) == 1:
            vector = args[0]
            # Assume subscriptable
            self.array = np.array(
                [vector[0], vector[1]])
        elif len(args) == 2:
            # assume initialization by start and stop
            start = args[0]
            stop = args[1]
            self.array = np.array([stop[0]-start[0], stop[1]-start[1]])
        self.array = np.round(self.array, decimals=3)

    def __getitem__(self, item):
        return self.array[item]

    def __add__(self, other):
        if other is None:
            return self
        try:
            # if other is subscriptable
            return Vector((self[0] + other[0], self[1] + other[1]))
        except:
            # Assume scalar
            return Vector((self[0] + other, self[1] + other))

    def __sub__(self, other):
        if other is None:
            return self
        return self + (other * (-1))

    def __mul__(self, other):
        if other is None:
            return None
        return Vector(self.array*other)

    def __truediv__(self, other):
        return Vector(self.array/other)

    def __neg__(self):
        return Vector(-self.array)

    def __len__(self):
        return np.sqrt(self[0]**2 + self[1]**2)

    def __str__(self) -> str:
        return f'Vector({self[0]},{self[1]})'

    def __repr__(self) -> str:
        return f'Vector({self[0]},{self[1]})'

    def normalize(self):
        return Vector(self) / (np.sqrt(self[0]**2 + self[1]**2))

    def x(self):
        return self.array[0]

    def y(self):
        return self.array[1]

    def to_coordinate(self):
        return Coordinate(self)

    def rotate(self, angle):
        """
        Rotate vector by specified angle
        Returns the rotated version of the vector
        """
        # Rotation matrix:
        angle_rad = np.deg2rad(angle)
        Rmat = np.array([[np.cos(angle_rad), -np.sin(angle_rad)], [np.sin(angle_rad), np.cos(angle_rad)]])
        rot_array = Rmat@self.array
        return Vector(np.round(rot_array, decimals=4))

    def quadrant(self):
        """
        Return the quadrant
        """
        if self[0] > 0 and self[1] > 0:
            return 1
        elif self[0] < 0 and self[1] > 0:
            return 2
        elif self[0] < 0 and self[1] < 0:
            return 3
        else:
            return 4

class Line:
    """
    A line is a vector + a start cooridinate
    """
    def __init__(self, start: Coordinate, vector: Vector) -> None:
        self.start = start
        self.vector = vector

