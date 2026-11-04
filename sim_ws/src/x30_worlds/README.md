# x30_worlds

Gazebo Harmonic worlds, their models and ground-truth data. No nodes, no
topics: it only installs files and makes Gazebo able to find the models.

Currently contains one world, `aws_hospital`. The built-in `default_arena` and
`lab_room` worlds live in `x30_sim`.

## Layout

```
worlds/aws_hospital/
    world.sdf       the Gazebo world
    objects.json    ground-truth objects (read by x30_sim ground_truth)
    map.yaml/png    2D occupancy map of the floor plan
    meta.json       world metadata
    preview.png
config/labels.yaml  semantic label table (class id, kind, synonyms, nav_target)
hooks/x30_worlds.dsv.in
models/             69 models, generated locally, NOT in Git
```

## Build

`ament_cmake`, no compilation. `CMakeLists.txt` installs `worlds/`, `config/`
and, when present, `models/` into `share/x30_worlds`. The environment hook
`x30_worlds.dsv.in` adds `<share>/x30_worlds/models` to `GZ_SIM_RESOURCE_PATH`
so `model://` URIs resolve after sourcing the workspace.

The Docker build copies `sim_ws/src`, so `models/` must exist **before**
building the image:

```bash
python3 docker/sim/prepare_hospital.py          # download and convert models
python3 docker/sim/prepare_hospital.py --check  # verify only, no download
```

The script restores the 69 referenced models, with AWS models at a pinned git
revision and Fuel model versions and archive checksums recorded in
`docker/sim/hospital-assets.lock.json`. It applies the Classic-to-Harmonic
model cleanup and keeps each model's licence and attribution. It resumes from
completed models if interrupted.

## The aws_hospital world

Registered in `configs/sim/worlds.yaml`: spawn (0.93, 11.48, yaw 0), bounds
x −14.5..14.5, y −37..23.2, 181 includes, 124 labelled objects, 781.6 m²
navigable. Objects include 30 chairs, 20 carts, 13 people, 12 medical devices,
8 cabinets, 7 shelves and 6 toilets.

## Licences

AWS models MIT-0; OpenRobotics Fuel models CC BY 4.0 (attribution kept beside
each model).

## Building on it

- **Add a world**: create `worlds/<id>/world.sdf` with `objects.json` and
  `map.yaml` if you need ground truth and a map, then add an entry under
  `worlds:` in `configs/sim/worlds.yaml` (`sdf`, `spawn`, `bounds`,
  `objects_file`, `map_file`). Launch with `world:=<id>`.
- **Label objects** so they appear in `/gt/objects`, in this order of
  precedence: an `<x30:label>` element in the model, a Gazebo Label plugin id
  mapped through `config/labels.yaml`, or the model name with its instance
  suffix removed (`chair_3` becomes `chair`). Unlabelled models count as
  structure.
- **Add a model**: put it under `models/<name>/`, keep its licence file, and
  rebuild so it is installed.
- **Add a label class**: add it to `config/labels.yaml` with a unique `id`.
