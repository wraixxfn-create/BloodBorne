# Arena Mesh Kit — Modular 3D Assets

This folder contains 87 original OBJ meshes for the Hollow Sanctum boss arena.

## Categories
- Floor: 400x400, 200x200, 100x100, Wedge 22.5° r15-19, Edge, Ritual Plate, Ritual Center
- Wall: 400x400, 400x800, 400x1600, Window variants, Buttress, Base, Cornice
- Pillar: Base, Shaft, Capital, Full 14m, Damaged 14m, LOD1
- Arch: 400x150 low broad, 300x400 tall, Ruined
- Window: Frame 300x400, Frame 520x950, Tracery Circle, Mullion, Glass Pane, Glass Shards Cluster
- Stairs: Step, Straight 3-step, Broad 4m, Curved Tier, Plate
- Platform: Slab, Cylinder 10m, Cylinder 14m, Rim, StepRing
- Statue: Pedestal, Torso, Head, Complete, Fallen, Debris, LOD1
- Chain: Link, Segment 6 links, Swag 5m, Anchor, Hook
- Wood: Beam 3.2m, Brace, Plank, Scaffold, Debris
- Candle: Wax small/tall, Brazier holder, Cluster 3x, Sconce
- Ritual: Brazier Large, Circle 3.2m, Rune, Chalice, Incense, Altar Slab
- Debris: Stone Small/Medium/Large, Glass Shards, Rubble Pile, Wood Splinters
- Door: Frame, Wood Heavy, Gate Iron, Sealed Stone
- Deco: Gargoyle, Cornice, Banner Tattered, Bracket, Candelabra, Fog Volume, Moss Patch
- LOD: Floor LOD1, Wall LOD1, Pillar LOD1, Statue LOD1

## Specs
- Pivot: base center (0,0,0) bottom, Y up
- Scale: 1 unit = 1 meter, dimensions in filename are cm (400 = 4.00 m)
- Topology: clean quads, 12-300 tris per mesh, hard edges where needed, smooth where needed
- UVs: planar/box projected 0-1 per face, cylindrical for cylinders
- Material slots: 1-2 per mesh, 3 max for complex (candle cluster, glass cluster)
- Materials: reference existing Arena mats (StoneFloor, StoneWall, StonePillar, Metal_Chain, Wood_Rotted, Statue_Eroded, Candle_Wax/Flame, RitualMarking, Fog_Plane, Brazier_Metal, Glass_Blue/Red/Amber) plus new Banner_Cloth, Moss, Door_Wood, Door_Iron, StoneTrim
- LOD: LOD1 versions are single boxes, same pivot/material

## Usage
- Prefabs in `Assets/Prefabs/Arena/MeshKit/` reference these meshes with correct materials and colliders
- Master assembly: `Assets/Prefabs/Arena/Arena_RitualChamber_MeshKit.prefab` (321 children)
- Scene: `Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`

## Grid
- Base grid 4 m, snap 4 m move, 22.5° rotate for circular
- Walls at radius 19 m, pillars at 17.5 m every 45°, floor wedges 22.5° r15-19
- Platform Tier1 14 m dia, Tier2 10 m dia, steps 0.3 m

## Optimization
- Total master ~8k verts, ~4k tris, ~30-40 draw calls after batching
- Point lights no shadows, spot + directional soft shadows only
- Mark Environment layer static for batching, add LODGroup for distant pillars/walls/statues

All meshes original, no external assets.
