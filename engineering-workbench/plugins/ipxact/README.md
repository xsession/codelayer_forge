# IP-XACT plugin boundary

This directory intentionally contains the interoperability boundary rather than FPGA/IP-XACT behavior in the graph core.

The first implementation target is an independently authored importer/exporter for IEEE 1685 component and design metadata. It should map:

- component -> `ComponentDefinition`
- physical port -> `PortDefinition`
- busInterface -> `InterfaceDefinition`
- design componentInstance -> `ComponentInstance`
- interconnection -> interface-level connection projection
- adHocConnection -> signal `Connection`

Implementation must be written from the applicable IEEE/Accellera specifications and independently created fixtures. Do not translate Kactus2 parsers or copy vendor-extension handling from Kactus2 source.

The current MVP deliberately leaves this plugin as a clean extension boundary while the generic connection engine is stabilized.
