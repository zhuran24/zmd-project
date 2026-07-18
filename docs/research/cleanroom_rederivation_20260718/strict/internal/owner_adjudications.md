# Owner Adjudications for Ambiguous Game Semantics

These rulings close the routing questions identified while preparing the neutral package. They are benchmark authority but remain hidden until both independent derivation rounds finish.

## Access-Cell Occupancy

A transport unit may occupy the first cell outside an active facility port. Legal units are a straight segment, turn, crossing, splitter, or merger. Facility bodies cannot occupy an active port's access cell. An inactive port makes no claim on that cell and may face outside the map.

## Direction Compatibility

- An output port facing direction `d` connects to a component that includes `opposite(d)` among its inputs.
- An input port facing direction `d` connects to a component that includes `opposite(d)` among its outputs.

A straight component can therefore connect a facing output and input through one shared cell. Two outputs may feed one merger. One splitter may feed two inputs.

## Sharing

One transport component connects every adjacent active terminal whose direction is compatible. It is not limited to one terminal or one commodity. Multi-commodity sharing, merging, and splitting are legal. A crossing consists of two perpendicular straight channels and does not transfer material between the channels.

Two same-direction ports cannot share one access cell without overlapping their facility bodies, so that apparent case is geometrically impossible rather than a separate routing prohibition.
