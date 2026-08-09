# Factory Layout Optimality Benchmark

This is a self-contained architecture and proof-design problem. Assume no existing implementation.

## Goal

Place all required facilities on a 70 by 70 cell grid, add any number of allowed auxiliary facilities, and connect every required material terminal. Among the remaining cells, maximize the largest axis-aligned rectangle containing no facility body cells. Compare solutions lexicographically by rectangle area and then shorter side; rectangles with a side below 6 are inadmissible.

The requested result is both a feasible layout and an auditable argument that no better objective value exists. A heuristic layout alone is insufficient.

## Authoritative Data

`problem_instance.json` is the machine-readable authority. Coordinates are zero-based with the origin at the southwest corner. A mode gives body-local port cells and outward directions. The access cell of a port is the adjacent cell in that direction.

All required facility bodies must remain in the grid and bodies may not overlap. A body may touch the map boundary. Only a bound, active port needs its access cell to be in the grid and free of facility bodies; an unbound port may face outside the grid or be blocked.

The instance has 219 manufacturing facilities in 17 operation groups, one protocol core, and 46 boundary storage ports. Power poles and storage boxes are repeatable auxiliaries. The data lists exact per-facility material terminal counts, all 19 commodities, and every required instance identifier.

## Material Terminals

Manufacturing terminals accept only the commodity specified by their operation. Counts are exact. Boundary storage ports and protocol-core outputs jointly provide the exact raw-output requirements. Final products must enter active input terminals on the protocol core or storage boxes. Storage-box outputs must remain inactive in this benchmark.

Every active output must reach an active input of the same commodity, and every active input must be reached by an active output. Separate connected regions for one commodity are allowed. Intermediate products may not use storage as a teleporting transfer.

## Transport Components

Transport occupies grid cells outside facility bodies. A straight has one input and the opposite output; a turn has one input and one perpendicular output. A splitter has one input and two or three distinct other outputs; a merger has two or three distinct inputs and one other output. A crossing is exactly two perpendicular straight channels with no transfer between channels. Directions within a component or channel are unique. One component may carry multiple commodities and connects every direction-compatible adjacent active terminal. Capacity and throughput are outside this benchmark.

For a facility output facing direction `d`, a component in its access cell must include `opposite(d)` among its inputs. For a facility input, that component must include `opposite(d)` among its outputs. Thus two outputs may join through a merger and two inputs may be served through a splitter.

## Power

A pole has a 2 by 2 body. From anchor `(x,y)`, its inclusive coverage is `x-5..x+6` by `y-5..y+6`, clipped to the map. Every facility marked `requires_power` must have at least one body cell in some pole's coverage. Pole bodies also participate in non-overlap and in the empty-rectangle objective.

## Deliverable

Design a system capable of producing and auditing an optimality result on one Linux machine with 24 CPU cores and 48 GB memory. Explain:

1. whether the system is monolithic or decomposed, and why;
2. where each geometry, terminal, routing, power, and objective rule is enforced;
3. what information components exchange, including the form of a rejection explanation;
4. the three most likely failure modes and mitigations;
5. CPU, memory, and wall-clock allocation; and
6. how feasibility and the upper-bound argument are independently checked.

Do not assume a particular solver or proof technology. State every additional assumption.
