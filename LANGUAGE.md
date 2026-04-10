# CLIGEBRA Language

This file describes the CLIGEBRA scene language only.

## Overview

A CLIGEBRA file is a list of object definitions, one per line.

Blank lines and lines starting with `#` are ignored.

Example:

```text
# points
p1 = (0, 0, 0)
p2 = (4, 6, 0)

# vectors
v1 = vec[1, 2, 0]

# line
l1 = line(p1, p2)

# plane
E = plane(p1, vec[0, 0, 1])

# cylinder
c1 = cyl(p1, (0, 0, 5), 1)
```

## Object Definitions

You can define objects in two ways:

```text
name = expression
kind name = expression
```

Examples:

```text
p1 = (0, 0, 0)
point p1 = (0, 0, 0)

v1 = vec[1, 2, 0]
vector v1 = vec[1, 2, 0]
```

Unnamed objects are also allowed:

```text
(0, 0, 0)
vec[1, 2, 0]
cyl((0,0,0), (0,0,5), 1)
```

## Points

Points use parentheses:

```text
p1 = (x, y, z)
```

Examples:

```text
p1 = (0, 0, 0)
p2 = (4, -3, 7)
```

## Vectors

Vectors use `vec[...]`:

```text
v1 = vec[x, y, z]
```

Examples:

```text
v1 = vec[1, 2, 0]
v2 = vec[0, 0, 1]
```

## Lines

### Preferred forms

Line through a point and a vector:

```text
l1 = line(p1, v1)
l1 = line((0,0,0), vec[1,2,0])
l1 = line((0,0,0), [1,2,0])
l1 = line((0,0,0), (1,2,0))
```

Line through two points:

```text
l1 = line(p1, p2)
l1 = line((0,0,0), (4,6,0))
```

### Legacy form

This older form is still accepted:

```text
l1 = line(point(0,0,0), dir(1,1,0))
```

### Notes

- In `line(p1, p2)`, the two points must be different.
- In `line(p1, v1)`, the vector must be non-zero.
- Named points and named vectors must be defined earlier in the file.

## Planes

### Equation form

Planes can be written as equations:

```text
E = 2x + y + 2z - 8 = 0
floor = z = 0
wall = x - 3 = 0
```

### Point + normal form

```text
E = plane(p1, vec[0,0,1])
E = plane((0,0,0), vec[0,0,1])
```

This means: plane through the point with the given normal vector.

### Three-point form

```text
E = plane(p1, p2, p3)
E = plane((0,0,0), (1,0,0), (0,1,0))
```

This means: plane through three points.

Rules:

- the three points must not be collinear
- named points must be defined earlier in the file

### Point + two-vector form

```text
E = plane(p1, v1, v2)
E = plane((0,0,0), vec[1,0,0], vec[0,1,0])
```

This means: plane through the point, spanned by the two vectors.

Rules:

- the two vectors must not be parallel
- named vectors must be defined earlier in the file

### Legacy point/normal form

This older form is still accepted:

```text
E = point(0,0,0) normal vec[0,0,1]
```

## Cylinders

### Preferred forms

Cylinders use:

```text
c1 = cyl(start_point, end_point, radius)
```

Examples:

```text
c1 = cyl((0,0,0), (0,0,5), 1)
c1 = cyl(p1, p2, 3)
```

### Compatibility alias

The older spelling still works:

```text
c1 = zyl((0,0,0), (0,0,5), 1)
```

### Rules

- radius must be greater than `0`
- start and end must be different points
- endpoints can be literal points or named points
- named points must be defined earlier in the file

## References

Named objects can be reused in later expressions.

Currently:

- points can be reused in `line(...)`, `plane(...)`, and `cyl(...)`
- vectors can be reused in `line(...)` and `plane(...)`

Example:

```text
p1 = (1, 2, 3)
p2 = (4, 6, 3)
v1 = vec[0, 1, 0]
v2 = vec[0, 0, 1]

l1 = line(p1, v1)
l2 = line(p1, p2)
E1 = plane(p1, v1)
E2 = plane(p1, p2, (1,2,7))
E3 = plane(p1, v1, v2)
c1 = cyl(p1, p2, 0.5)
```

## Comments

Comments start with `#`:

```text
# this is a comment
p1 = (0, 0, 0)
```

## Minimal Example

```text
# points
p1 = (4,5,23)
p2 = (14,-13,23)
p3 = (4,5,28)

# vectors
v1 = vec[0,0,1]
v2 = vec[1,0,0]

# geometry
l1 = line(p1, p2)
E1 = plane(p1, p2, p3)
E2 = plane(p1, v1, v2)
c1 = cyl(p1, p2, 3)
```
