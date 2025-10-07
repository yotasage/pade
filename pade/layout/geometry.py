import numpy as np
import copy
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True) # This makes the Coordiante immutable
class Coordinate:
    x: float
    y: float

    def to_skill(self, decimals=3):
        return f"{round(self.x, decimals)}:{round(self.y, decimals)}"

    def to_list(self, decimals=3):
        return [np.round(self.x, decimals=decimals), np.round(self.y, decimals=decimals)]

    def __iter__(self):
        yield self.x
        yield self.y

    def tuple(self):
        return (self.x, self.y)

    def __round__(self, ndigits=0):
        return Coordinate((round(self[0], ndigits), round(self[1], ndigits)))

    def __getitem__(self, item):
        if item == 0:
            return self.x
        elif item == 1:
            return self.y
        else:
            raise ValueError(f'Invalid index for coordinate {item}')

    def __add__(self, other):
        """
        Assumes other is subscriptable
        """
        if other is None:
            return self
        try:
            return Coordinate((self[0] + other[0], self[1] + other[1]))
        except:
            return Coordinate((self[0] + other, self[1] + other))

    def __sub__(self, other):
        """
        Assumes other is subscriptable
        """
        if other is None:
            return self
        try:
            return Coordinate((self[0] - other[0], self[1] - other[1]))
        except:
            return Coordinate((self[0] - other, self[1] - other))
        
    def __truediv__ (self, value: float):
        return Coordinate((self[0] / value, self[1] / value))

    def __mul__(self, scalar: float):
        return Coordinate(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __str__(self) -> str:
        return f'Coordinate({self[0]},{self[1]})'

    def __repr__(self) -> str:
        return f'Coordinate({self[0]},{self[1]})'
    
    def translate(self, dx=0, dy=0):
        return Coordinate(self.x + dx, self.y + dy)
    
    @classmethod
    def midpoint(cls, a: 'Coordinate', b: 'Coordinate'):
        return cls.avg([a, b])
    
    @classmethod
    def avg(cls, coords: Iterable['Coordinate']):
        if not coords:
            raise ValueError("Cannot calculate average of empty coordinate list")
    
        coords = list(coords) # supports any iterable

        total = sum(coords[1:], coords[0])
        return total / len(coords)

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

