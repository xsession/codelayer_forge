# Standalone demo

This is a zero-dependency browser implementation of the current workbench MVP.

## Run

From the repository root:

```bash
python3 -m http.server 8765 -d standalone
```

Open `http://localhost:8765`.

## Try these interactions

- Drag a component from **Library** onto the canvas.
- Drag a node by its header; position snaps to a 10-unit grid.
- Drag from a port marker to another port marker.
- Compatible targets turn green, warnings amber, incompatible targets fade/red.
- Click a wire; its invisible hit target is much wider than its visible stroke.
- Delete the selected connection using the Inspector or `Delete`.
- Rename a selected component in the Inspector.
- Use `Ctrl+Z` / `Ctrl+Y` for undo/redo.
- Use the mouse wheel to zoom around the pointer.
- Shift-drag or middle-drag to pan.
- Inspect **Problems** and **Connections** in the bottom dock.
