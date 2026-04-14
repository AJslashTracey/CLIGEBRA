# CLIGEBRA Language

This file shows the normal CLIGEBRA forms only.

## Basics

A `.clg` file is a list of object definitions, one per line:

```text
name = expression
```

Blank lines and lines starting with `#` are ignored.

Example:

```text
p1 = (0, 0, 0)
p2 = (4, 6, 0)
v1 = vec[0, 0, 1]
l1 = line(p1, p2)
E = plane(p1, v1)
c1 = cyl(p1, p2, 1)
s1 = sphere(p1, 2)
```

## Points

```text
p1 = (x, y, z)
```

Example:

```text
p1 = (0, 0, 0)
```

## Vectors

```text
v1 = vec[x, y, z]
```

Example:

```text
v1 = vec[1, 2, 0]
```

## Lines

Through two points:

```text
l1 = line(p1, p2)
```

Through a point and a vector:

```text
l1 = line(p1, v1)
```

Examples:

```text
l1 = line((0, 0, 0), (4, 6, 0))
l2 = line((0, 0, 0), vec[1, 2, 0])
```

## Planes

Equation form:

```text
E = 2x + y - 2z = 0
```

Point and normal vector:

```text
E = plane(p1, v1)
```

Example:

```text
E = plane((0, 0, 0), vec[0, 0, 1])
```

## Cylinders

```text
c1 = cyl(start_point, end_point, radius)
```

Example:

```text
c1 = cyl((0, 0, 0), (0, 0, 5), 1)
```

## Spheres

```text
s1 = sphere(center_point, radius)
```

Example:

```text
s1 = sphere((0, 0, 0), 2)
```

## References

You can reuse names that were defined earlier in the file.

Example:

```text
p1 = (0, 0, 0)
p2 = (4, 0, 0)
v1 = vec[0, 0, 1]
l1 = line(p1, p2)
E = plane(p1, v1)
c1 = cyl(p1, p2, 0.5)
s1 = sphere(p1, 2)
```
