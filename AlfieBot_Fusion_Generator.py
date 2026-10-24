"""
AlfieBot_Fusion_Generator.py - AlfieBot V0.1 parametric assembly generator.

Run from Autodesk Fusion: Utilities > Add-Ins > Scripts and Add-Ins.

What it does
------------
Creates a new parametric Fusion design containing the AlfieBot_V0.1
assembly: eleven native components built from sketches and features
(extrude, fillet, shell, combine, hole, mirror, circular and rectangular
patterns) that are all driven by named user parameters. It then applies
appearances, adds as-built rigid joints, and writes a validation report.

Build order (matches the V0.1 development stages)
    Stage A  Main rounded body (box > fillet > shell > rear split)
    Stage B  Front face opening, bezel, display placeholder, eye graphics
    Stage C  Side speaker holes, accent rings, speaker grilles
    Stage D  Top button and feet
    Stage E  Rear cover and electronics tray
    Stage F  Appearances, joints, view and validation

Coordinate system
    X = width (left -X to right +X), Y = depth (front -Y to rear +Y),
    Z = height (Z = 0 is the underside of the feet).
    Every component origin coincides with the assembly origin and every
    occurrence uses the identity transform, so each component is modelled
    in place in assembly coordinates.

Units
    User parameters are in mm. Fusion's API works in cm internally, so all
    feature sizes are passed as parameter expressions (strings) and Fusion
    does the conversion. Numeric values are only used to place initial
    sketch geometry, which is then locked by parameter-driven dimensions.

Status
    This script was written without access to Fusion and has not yet been
    executed. Run it, then read AlfieBot_Validation_Report.txt.
"""

import adsk.core
import adsk.fusion
import importlib
import math
import os
import sys
import time
import traceback

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
import alfiebot_parameters as AP  # noqa: E402

# Pick up edits to the parameter table without restarting Fusion.
importlib.reload(AP)

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

CREATE_NEW_DOCUMENT = True      # Build in a new design rather than the active one
CREATE_EYE_GRAPHICS = True      # Visual-only eye discs on the display
APPLY_APPEARANCES = True
CREATE_JOINTS = True            # Ground Main_Body, as-built rigid joints for the rest
RUN_VALIDATION = True
RUN_PARAMETER_FLEX_TEST = True  # Temporarily edits parameters, then restores them
REPORT_FILE_NAME = "AlfieBot_Validation_Report.txt"

# ---------------------------------------------------------------------------
# Globals and logging
# ---------------------------------------------------------------------------

_app = None
_ui = None
_log_lines = []

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

X_POS, X_NEG = (1, 0, 0), (-1, 0, 0)
Y_POS, Y_NEG = (0, 1, 0), (0, -1, 0)
Z_POS, Z_NEG = (0, 0, 1), (0, 0, -1)


def log(message, level="INFO"):
    line = "[%s] %s" % (level, message)
    _log_lines.append(line)
    try:
        _app.log(line)  # Text Commands window
    except Exception:
        pass


def vi(expression):
    """ValueInput from a Fusion expression string, e.g. 'body_width/2 + 1 mm'."""
    return adsk.core.ValueInput.createByString(str(expression))


def collection(items):
    coll = adsk.core.ObjectCollection.create()
    for item in items:
        coll.add(item)
    return coll


def point(x, y, z=0.0):
    return adsk.core.Point3D.create(x, y, z)


def vector(direction):
    return adsk.core.Vector3D.create(*[float(c) for c in direction])


def side_expr(sign, expression):
    """Mirror an X expression to the -X side."""
    return expression if sign > 0 else "-(%s)" % expression


class StageError(Exception):
    pass


# ---------------------------------------------------------------------------
# PartBuilder: parametric modelling helpers bound to one component
# ---------------------------------------------------------------------------


class PartBuilder:
    """Creates sketches and features inside one component.

    Positions are expressed as parameter expressions measured along the
    assembly axes. Construction planes are offset from the component's own
    origin planes, construction points are made from three planes, and sketch
    geometry is dimensioned from those projected points, so every feature
    follows the user parameters.
    """

    _ZERO = (None, "", "0", "0 mm")

    def __init__(self, design, occurrence):
        self.design = design
        self.occ = occurrence
        self.comp = occurrence.component
        self.feats = self.comp.features
        self._planes = {}
        self._points = {}

    # -- evaluation -------------------------------------------------------
    def cm(self, expression):
        """Evaluate a length expression to Fusion internal units (cm)."""
        return self.design.unitsManager.evaluateExpression(str(expression), "mm")

    def body(self, name):
        found = self.comp.bRepBodies.itemByName(name)
        if not found:
            raise StageError("%s: body '%s' not found" % (self.comp.name, name))
        return found

    # -- construction geometry --------------------------------------------
    def plane(self, axis, expression=None):
        """Construction plane normal to `axis` ('x'/'y'/'z') at coordinate `expression`."""
        base = {
            "x": self.comp.yZConstructionPlane,
            "y": self.comp.xZConstructionPlane,
            "z": self.comp.xYConstructionPlane,
        }[axis]
        if expression in self._ZERO:
            return base
        key = (axis, expression)
        if key in self._planes:
            return self._planes[key]
        normal = base.geometry.normal
        along = {"x": normal.x, "y": normal.y, "z": normal.z}[axis]
        # Offsets are measured along the plane normal; flip if that points down the axis.
        offset = expression if along > 0 else "-(%s)" % expression
        plane_input = self.comp.constructionPlanes.createInput()
        plane_input.setByOffset(base, vi(offset))
        plane = self.comp.constructionPlanes.add(plane_input)
        try:
            plane.name = "%s = %s" % (axis.upper(), expression)
        except Exception:
            pass
        plane.isLightBulbOn = False
        self._planes[key] = plane
        return plane

    def anchor(self, x=None, y=None, z=None):
        """Construction point at (x, y, z) built from three parametric planes."""
        if x in self._ZERO and y in self._ZERO and z in self._ZERO:
            return self.comp.originConstructionPoint
        key = (x, y, z)
        if key in self._points:
            return self._points[key]
        point_input = self.comp.constructionPoints.createInput()
        point_input.setByThreePlanes(self.plane("x", x), self.plane("y", y), self.plane("z", z))
        cpoint = self.comp.constructionPoints.add(point_input)
        cpoint.isLightBulbOn = False
        self._points[key] = cpoint
        return cpoint

    def axis_from_face(self, cylindrical_face, name):
        axis_input = self.comp.constructionAxes.createInput()
        axis_input.setByCircularFace(cylindrical_face)
        axis = self.comp.constructionAxes.add(axis_input)
        axis.name = name
        axis.isLightBulbOn = False
        return axis

    # -- sketches ---------------------------------------------------------
    def sketch(self, axis, expression, name):
        sk = self.comp.sketches.add(self.plane(axis, expression))
        sk.name = name
        return sk

    def sketch_on_face(self, face, name):
        sk = self.comp.sketches.add(face)
        sk.name = name
        return sk

    @staticmethod
    def project(sk, construction_point):
        """Project a construction point into a sketch and return the sketch point."""
        return sk.project(construction_point).item(0)

    @staticmethod
    def _sketch_direction(sk, axis):
        """'h' if the model axis runs along the sketch X axis, otherwise 'v'."""
        xd = sk.xDirection
        return "h" if abs({"x": xd.x, "y": xd.y, "z": xd.z}[axis]) > 0.9 else "v"

    def rect(self, sk, centre, half):
        """Rectangle centred on sketch point `centre`.

        half: {model_axis: half_size_expression} for the two in-plane axes.
        Four lines, horizontal/vertical constraints and four driven
        dimensions from the centre point to two opposite corners.
        """
        sizes = {}
        for axis, expression in half.items():
            sizes[self._sketch_direction(sk, axis)] = (expression, self.cm(expression))
        if set(sizes) != {"h", "v"}:
            raise StageError("rect(): axes %s are not both in sketch '%s'" % (list(half), sk.name))
        (h_expr, hu), (v_expr, hv) = sizes["h"], sizes["v"]
        c = centre.geometry
        lines = sk.sketchCurves.sketchLines
        l0 = lines.addByTwoPoints(point(c.x - hu, c.y - hv), point(c.x + hu, c.y - hv))
        l1 = lines.addByTwoPoints(l0.endSketchPoint, point(c.x + hu, c.y + hv))
        l2 = lines.addByTwoPoints(l1.endSketchPoint, point(c.x - hu, c.y + hv))
        l3 = lines.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)
        constraints = sk.geometricConstraints
        constraints.addHorizontal(l0)
        constraints.addVertical(l1)
        constraints.addHorizontal(l2)
        constraints.addVertical(l3)
        dims = sk.sketchDimensions
        horizontal = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        vertical = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        for corner, sign in ((l0.startSketchPoint, -1), (l1.endSketchPoint, 1)):
            d = dims.addDistanceDimension(centre, corner, horizontal, point(c.x + sign * hu / 2, c.y + sign * (hv + 0.5)))
            d.parameter.expression = h_expr
            d = dims.addDistanceDimension(centre, corner, vertical, point(c.x + sign * (hu + 0.5), c.y + sign * hv / 2))
            d.parameter.expression = v_expr
        return [l0, l1, l2, l3]

    def circle(self, sk, centre, diameter_expression):
        """Circle on sketch point `centre` with a parameter-driven diameter."""
        r = self.cm(diameter_expression) / 2
        c = centre.geometry
        circ = sk.sketchCurves.sketchCircles.addByCenterRadius(centre, r)
        d = sk.sketchDimensions.addDiameterDimension(circ, point(c.x + r * 0.7, c.y + r * 0.7))
        d.parameter.expression = diameter_expression
        return circ

    def radial_point(self, sk, centre, radius_expression, direction):
        """Sketch point at a driven distance from `centre` along up/right/down."""
        r = self.cm(radius_expression)
        dx, dy = {"up": (0, r), "right": (r, 0), "down": (0, -r)}[direction]
        c = centre.geometry
        line = sk.sketchCurves.sketchLines.addByTwoPoints(centre, point(c.x + dx, c.y + dy))
        line.isConstruction = True
        if dx == 0:
            sk.geometricConstraints.addVertical(line)
        else:
            sk.geometricConstraints.addHorizontal(line)
        d = sk.sketchDimensions.addDistanceDimension(
            line.startSketchPoint, line.endSketchPoint,
            adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
            point(c.x + dx / 2 + 0.3, c.y + dy / 2 + 0.3))
        d.parameter.expression = radius_expression
        return line.endSketchPoint

    @staticmethod
    def profiles(sk, loops=None):
        """All profiles, or only those with `loops` loops (2 = annulus)."""
        found = [p for p in sk.profiles if loops is None or p.profileLoops.count == loops]
        if not found:
            raise StageError("Sketch '%s' produced no matching profile" % sk.name)
        return found

    @staticmethod
    def profile_for_curve(sk, curve):
        for prof in sk.profiles:
            for loop in prof.profileLoops:
                for pc in loop.profileCurves:
                    if pc.sketchEntity == curve:
                        return prof
        raise StageError("No profile found for a curve in '%s'" % sk.name)

    # -- features ---------------------------------------------------------
    def extrude(self, profiles, distance, direction, operation, participants=None, name=None):
        """One-sided extrude of `distance` towards the model `direction`."""
        extrudes = self.feats.extrudeFeatures
        prof = profiles[0] if len(profiles) == 1 else collection(profiles)
        ext_input = extrudes.createInput(prof, operation)
        sk = profiles[0].parentSketch
        normal = sk.xDirection.crossProduct(sk.yDirection)
        side = (adsk.fusion.ExtentDirections.PositiveExtentDirection
                if normal.dotProduct(vector(direction)) > 0
                else adsk.fusion.ExtentDirections.NegativeExtentDirection)
        ext_input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(vi(distance)), side)
        if participants:
            ext_input.participantBodies = list(participants)
        feature = extrudes.add(ext_input)
        if name:
            feature.name = name
        return feature

    def extrude_symmetric(self, profiles, total_distance, operation, participants=None, name=None):
        extrudes = self.feats.extrudeFeatures
        prof = profiles[0] if len(profiles) == 1 else collection(profiles)
        ext_input = extrudes.createInput(prof, operation)
        ext_input.setSymmetricExtent(vi(total_distance), True)
        if participants:
            ext_input.participantBodies = list(participants)
        feature = extrudes.add(ext_input)
        if name:
            feature.name = name
        return feature

    def fillet(self, edges, radius, name):
        fillets = self.feats.filletFeatures
        fillet_input = fillets.createInput()
        try:
            # Current API (edge set inputs).
            fillet_input.edgeSetInputs.addConstantRadiusEdgeSet(collection(edges), vi(radius), True)
        except AttributeError:
            # Older Fusion builds.
            fillet_input.addConstantRadiusEdgeSet(collection(edges), vi(radius), True)
        fillet_input.isRollingBallCorner = True
        feature = fillets.add(fillet_input)
        feature.name = name
        return feature

    def shell(self, bodies, thickness, name):
        """Hollow closed bodies (no faces removed) with an inside wall."""
        shells = self.feats.shellFeatures
        shell_input = shells.createInput(collection(bodies), False)
        shell_input.insideThickness = vi(thickness)
        feature = shells.add(shell_input)
        feature.name = name
        return feature

    def combine(self, target, tools, operation, name):
        combines = self.feats.combineFeatures
        combine_input = combines.createInput(target, collection(tools))
        combine_input.operation = operation
        combine_input.isKeepToolBodies = False
        combine_input.isNewComponent = False
        feature = combines.add(combine_input)
        feature.name = name
        return feature

    def mirror(self, bodies, plane, name):
        mirrors = self.feats.mirrorFeatures
        feature = mirrors.add(mirrors.createInput(collection(bodies), plane))
        feature.name = name
        return [feature.bodies.item(i) for i in range(feature.bodies.count)]

    def circular_pattern(self, features, axis, count_expression, name):
        patterns = self.feats.circularPatternFeatures
        pattern_input = patterns.createInput(collection(features), axis)
        pattern_input.quantity = vi(count_expression)
        pattern_input.totalAngle = vi("360 deg")
        pattern_input.isSymmetric = False
        feature = patterns.add(pattern_input)
        feature.name = name
        return feature

    def rect_pattern(self, features, axis_one, count_one, spacing_one, name,
                     axis_two=None, count_two=None, spacing_two=None):
        patterns = self.feats.rectangularPatternFeatures
        pattern_input = patterns.createInput(
            collection(features), axis_one, vi(count_one), vi(spacing_one),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        if axis_two is not None:
            pattern_input.setDirectionTwo(axis_two, vi(count_two), vi(spacing_two))
        feature = patterns.add(pattern_input)
        feature.name = name
        return feature

    @staticmethod
    def edges_parallel(body, direction):
        """Straight edges of `body` parallel to the model `direction`."""
        d = vector(direction)
        found = []
        for edge in body.edges:
            geom = edge.geometry
            if geom.objectType != adsk.core.Line3D.classType():
                continue
            v = geom.startPoint.vectorTo(geom.endPoint)
            if v.length > 0 and abs(v.dotProduct(d)) / v.length > 0.999:
                found.append(edge)
        return found

    def rounded_prism(self, axis, plane_expression, centre_anchor, half, depth, direction, radius, body_name):
        """Rectangular prism with rounded corners (edges parallel to `direction`)."""
        sk = self.sketch(axis, plane_expression, body_name + " sketch")
        self.rect(sk, self.project(sk, centre_anchor), half)
        ext = self.extrude(self.profiles(sk), depth, direction, NEW, name=body_name + " extrude")
        body = ext.bodies.item(0)
        body.name = body_name
        edges = self.edges_parallel(body, direction)
        if len(edges) != 4:
            raise StageError("%s: expected 4 corner edges, found %d" % (body_name, len(edges)))
        self.fillet(edges, radius, body_name + " corners")
        return self.body(body_name)

    def hole(self, sk, sketch_point, diameter, depth, body_name, name):
        """Hole feature at a sketch point, falling back to an extrude cut.

        The fallback keeps the model buildable if the hole direction or API
        behaves differently in a given Fusion build; it is logged.
        """
        body = self.body(body_name)
        volume_before = body.volume
        try:
            holes = self.feats.holeFeatures
            hole_input = holes.createSimpleInput(vi(diameter))
            hole_input.setPositionBySketchPoint(sketch_point)
            hole_input.setDistanceExtent(vi(depth))
            hole_input.participantBodies = [body]
            feature = holes.add(hole_input)
            feature.name = name
            if self.body(body_name).volume < volume_before - 1e-9:
                return feature
            feature.deleteMe()
            log("%s: hole feature removed no material; using extrude cut instead" % name, "WARN")
        except Exception as exc:  # noqa: BLE001
            log("%s: hole feature failed (%s); using extrude cut instead" % (name, exc), "WARN")
        circ = self.circle(sk, sketch_point, diameter)
        prof = self.profile_for_curve(sk, circ)
        return self.extrude_symmetric([prof], "(%s)*2" % depth, CUT, [self.body(body_name)], name=name + " (cut)")


# ---------------------------------------------------------------------------
# Build context
# ---------------------------------------------------------------------------


class BuildContext:
    def __init__(self, design, assembly_occurrence):
        self.design = design
        self.asm_occ = assembly_occurrence
        self.asm = assembly_occurrence.component
        self.builders = {}
        self.stage_status = []

    def add_component(self, name):
        occ = self.asm.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name
        self.builders[name] = PartBuilder(self.design, occ)
        return self.builders[name]

    def b(self, name):
        return self.builders[name]


# ---------------------------------------------------------------------------
# Shared enclosure geometry
# ---------------------------------------------------------------------------


def build_rounded_hollow_box(b, body_name):
    """Box > fillet all 12 edges > shell inwards. Used by Main_Body and Rear_Cover."""
    sk = b.sketch("z", "foot_height", "Enclosure footprint")
    b.rect(sk, b.project(sk, b.anchor()), {"x": "body_width/2", "y": "body_depth/2"})
    ext = b.extrude(b.profiles(sk), "body_height", Z_POS, NEW, name="Enclosure block")
    body = ext.bodies.item(0)
    body.name = body_name
    b.fillet(list(body.edges), "corner_radius", "Enclosure edge fillets")
    b.shell([b.body(body_name)], "wall_thickness", "Enclosure shell")
    return b.body(body_name)


def cut_at_split(b, body_name, direction):
    """Remove everything on one side of the split plane (Y = split_y)."""
    sk = b.sketch("y", "split_y", "Split cut")
    b.rect(sk, b.project(sk, b.anchor(z="body_center_z")),
           {"x": "body_width/2 + 10 mm", "z": "body_height/2 + 10 mm"})
    b.extrude(b.profiles(sk), "body_depth", direction, CUT, [b.body(body_name)], name="Split cut")


# ---------------------------------------------------------------------------
# Stage A - main rounded body
# ---------------------------------------------------------------------------


def stage_a_main_body(ctx):
    b = ctx.b("Main_Body")
    build_rounded_hollow_box(b, "Main_Body")
    # Open the rear: the rear cover takes everything behind the split plane.
    cut_at_split(b, "Main_Body", Y_POS)


# ---------------------------------------------------------------------------
# Stage B - front face, bezel, display, eyes
# ---------------------------------------------------------------------------


def stage_b_front(ctx):
    # Face opening in the main body: rounded prism tool, combined as a cut.
    b = ctx.b("Main_Body")
    tool = b.rounded_prism(
        "y", "-body_depth/2 - 1 mm", b.anchor(z="face_center_z"),
        {"x": "face_width/2", "z": "face_height/2"},
        "corner_radius + 1 mm", Y_POS, "face_corner_radius", "Face opening tool")
    b.combine(b.body("Main_Body"), [tool], CUT, "Face opening")

    # Front bezel: a rounded plate inset by the clearance, with a display window.
    bz = ctx.b("Front_Bezel")
    centre = bz.anchor(z="face_center_z")
    bz.rounded_prism(
        "y", "-body_depth/2 + face_recess", centre,
        {"x": "face_width/2 - assembly_clearance", "z": "face_height/2 - assembly_clearance"},
        "bezel_thickness", Y_POS, "face_corner_radius - assembly_clearance", "Front_Bezel")
    window = bz.rounded_prism(
        "y", "-body_depth/2 + face_recess - 1 mm", centre,
        {"x": "display_width/2 - display_overlap", "z": "display_height/2 - display_overlap"},
        "bezel_thickness + 2 mm", Y_POS, "display_window_radius", "Display window tool")
    bz.combine(bz.body("Front_Bezel"), [window], CUT, "Display window")

    # Display placeholder: plain block behind the bezel.
    d = ctx.b("Display_Placeholder")
    sk = d.sketch("y", "display_front_y", "Display outline")
    d.rect(sk, d.project(sk, d.anchor(z="face_center_z")),
           {"x": "display_width/2", "z": "display_height/2"})
    ext = d.extrude(d.profiles(sk), "display_thickness", Y_POS, NEW, name="Display block")
    ext.bodies.item(0).name = "Display_Placeholder"

    if CREATE_EYE_GRAPHICS and "Eye_Graphics" in ctx.builders:
        build_eye_graphics(ctx.b("Eye_Graphics"))


def build_eye_graphics(e):
    """Visual-only eye rings and highlights on the display front (not printed)."""
    eye_z = "face_center_z + eye_offset_z"
    rings = e.sketch("y", "display_front_y", "Eye rings")
    highlights = e.sketch("y", "display_front_y", "Eye highlights")
    for sign in (-1, 1):
        x = side_expr(sign, "eye_spacing/2")
        c = e.project(rings, e.anchor(x=x, z=eye_z))
        e.circle(rings, c, "eye_diameter")
        e.circle(rings, c, "eye_diameter*0.55")
        hx = "%s + eye_diameter*0.1" % x
        hc = e.project(highlights, e.anchor(x=hx, z=eye_z + " + eye_diameter*0.1"))
        e.circle(highlights, hc, "eye_diameter*0.17")
    ext = e.extrude(e.profiles(rings, loops=2), "eye_graphic_thickness", Y_NEG, NEW, name="Eye rings")
    for i in range(ext.bodies.count):
        ext.bodies.item(i).name = "Eye_Ring_%d" % (i + 1)
    ext = e.extrude(e.profiles(highlights), "eye_graphic_thickness", Y_NEG, NEW, name="Eye highlights")
    for i in range(ext.bodies.count):
        ext.bodies.item(i).name = "Eye_Highlight_%d" % (i + 1)


# ---------------------------------------------------------------------------
# Stage C - speakers
# ---------------------------------------------------------------------------


def stage_c_speakers(ctx):
    # One symmetric cut through both side walls of the main body.
    b = ctx.b("Main_Body")
    sk = b.sketch("x", None, "Speaker holes")
    b.circle(sk, b.project(sk, b.anchor(y="module_center_y", z="body_center_z")), "speaker_hole_diameter")
    b.extrude_symmetric(b.profiles(sk), "body_width + 20 mm", CUT, [b.body("Main_Body")], name="Speaker holes")

    for side, sign in (("Left", -1), ("Right", 1)):
        build_accent_ring(ctx.b(side + "_Accent_Ring"), side, sign)
        build_speaker_grille(ctx.b(side + "_Speaker_Grille"), side, sign)


def build_accent_ring(r, side, sign):
    """Tube through the side wall + inner step (seats grille) + outer lip (stops ring)."""
    name = side + "_Accent_Ring"
    out = (sign, 0, 0)
    centre = r.anchor(y="module_center_y", z="body_center_z")
    inner_wall = side_expr(sign, "body_width/2 - wall_thickness")
    ring_id = "speaker_diameter + 2*assembly_clearance"

    sk = r.sketch("x", inner_wall, "Ring tube")
    c = r.project(sk, centre)
    r.circle(sk, c, ring_id)
    r.circle(sk, c, "speaker_hole_diameter - 2*assembly_clearance")
    ext = r.extrude(r.profiles(sk, loops=2), "wall_thickness", out, NEW, name="Ring tube")
    ext.bodies.item(0).name = name

    sk = r.sketch("x", inner_wall, "Ring grille step")
    c = r.project(sk, centre)
    r.circle(sk, c, "speaker_diameter - 2*grille_step_width")
    r.circle(sk, c, ring_id)
    r.extrude(r.profiles(sk, loops=2), "grille_step", out, JOIN, [r.body(name)], name="Ring grille step")

    sk = r.sketch("x", side_expr(sign, "body_width/2"), "Ring lip")
    c = r.project(sk, centre)
    r.circle(sk, c, ring_id)
    r.circle(sk, c, "speaker_hole_diameter + 2*accent_ring_lip")
    r.extrude(r.profiles(sk, loops=2), "accent_ring_protrusion", out, JOIN, [r.body(name)], name="Ring lip")


def build_speaker_grille(g, side, sign):
    """Disc seated on the ring step, outer face flush with the side wall, hole pattern."""
    name = side + "_Speaker_Grille"
    centre = g.anchor(y="module_center_y", z="body_center_z")
    sk = g.sketch("x", side_expr(sign, "body_width/2 - wall_thickness + grille_step"), "Grille disc")
    g.circle(sk, g.project(sk, centre), "speaker_diameter")
    ext = g.extrude(g.profiles(sk), "wall_thickness - grille_step", (sign, 0, 0), NEW, name="Grille disc")
    ext.bodies.item(0).name = name

    axis = g.axis_from_face(ext.sideFaces.item(0), "Grille axis")
    face_sketch = g.sketch_on_face(ext.endFaces.item(0), "Grille holes")
    c = g.project(face_sketch, centre)
    depth = "wall_thickness"
    g.hole(face_sketch, c, "grille_hole_diameter", depth, name, "Grille centre hole")
    for index, (fraction, count_name, direction) in enumerate(AP.GRILLE_RINGS, start=1):
        seed = g.radial_point(face_sketch, c, "speaker_diameter*%s" % fraction, direction)
        hole = g.hole(face_sketch, seed, "grille_hole_diameter", depth, name, "Grille ring %d seed" % index)
        g.circular_pattern([hole], axis, count_name, "Grille ring %d pattern" % index)


# ---------------------------------------------------------------------------
# Stage D - top button and feet
# ---------------------------------------------------------------------------


def stage_d_button_feet(ctx):
    # Button hole through the top wall.
    b = ctx.b("Main_Body")
    sk = b.sketch("z", "body_top_z + 1 mm", "Button hole")
    b.circle(sk, b.project(sk, b.anchor(y="module_center_y")), "button_diameter + 2*assembly_clearance")
    b.extrude(b.profiles(sk), "wall_thickness + 2 mm", Z_NEG, CUT, [b.body("Main_Body")], name="Button hole")

    build_top_button(ctx.b("Top_Button"))
    build_feet(ctx.b("Feet"))


def build_top_button(t):
    """Flange under the top wall (retains the button), stem/cap through the hole, accent inlay."""
    centre = t.anchor(y="module_center_y")
    sk = t.sketch("z", "body_top_z - wall_thickness - button_travel", "Button base")
    c = t.project(sk, centre)
    t.circle(sk, c, "button_diameter")
    t.circle(sk, c, "button_diameter + 2*button_flange_width")
    flange = t.extrude(t.profiles(sk), "button_flange_thickness", Z_NEG, NEW, name="Button flange")
    flange.bodies.item(0).name = "Button_Cap"

    disc = [p for p in t.profiles(sk, loops=1)]
    stem = t.extrude(disc, "wall_thickness + button_travel + button_height", Z_POS, JOIN,
                     [t.body("Button_Cap")], name="Button stem and cap")
    top_edges = list(stem.endFaces.item(0).edges)
    t.fillet(top_edges, "button_top_fillet", "Button top fillet")

    sk = t.sketch("z", "body_top_z + button_height", "Button accent")
    c = t.project(sk, centre)
    t.circle(sk, c, "button_diameter*%s" % AP.BUTTON_ACCENT_INNER)
    t.circle(sk, c, "button_diameter*%s" % AP.BUTTON_ACCENT_OUTER)
    ring = t.profiles(sk, loops=2)
    t.extrude(ring, "button_accent_depth", Z_NEG, CUT, [t.body("Button_Cap")], name="Accent groove")
    accent = t.extrude(ring, "button_accent_depth", Z_NEG, NEW, name="Accent inlay")
    accent.bodies.item(0).name = "Button_Accent"


def build_feet(f):
    """One foot, mirrored across X = 0, then across Y = module_center_y."""
    sk = f.sketch("z", None, "Foot")
    f.circle(sk, f.project(sk, f.anchor(x="foot_x", y="foot_front_y")), "foot_diameter")
    ext = f.extrude(f.profiles(sk), "foot_height", Z_POS, NEW, name="Foot")
    ext.bodies.item(0).name = "Foot_Front_Right"
    f.fillet(list(ext.startFaces.item(0).edges), "foot_fillet", "Foot bottom fillet")
    left = f.mirror([f.body("Foot_Front_Right")], f.comp.yZConstructionPlane, "Feet mirror X")
    if left:
        left[0].name = "Foot_Front_Left"
    rear = f.mirror([f.body("Foot_Front_Right"), f.body("Foot_Front_Left")],
                    f.plane("y", "module_center_y"), "Feet mirror Y")
    for body in rear:
        # Name by position; mirror result order is not guaranteed.
        bb = body.boundingBox
        body.name = "Foot_Rear_Right" if bb.minPoint.x + bb.maxPoint.x > 0 else "Foot_Rear_Left"


# ---------------------------------------------------------------------------
# Stage E - rear cover and electronics tray
# ---------------------------------------------------------------------------


def stage_e_rear_tray(ctx):
    build_rear_cover(ctx.b("Rear_Cover"))
    build_electronics_tray(ctx.b("Electronics_Tray"))


def build_rear_cover(r):
    name = "Rear_Cover"
    # Same rounded shell as the main body, keeping only the part behind the split.
    build_rounded_hollow_box(r, name)
    cut_at_split(r, name, Y_NEG)

    # Locating tabs (top, left, right) that slide into the main body with
    # clearance. Each tab has a root ("bridge") fused into the cover wall.
    # There is no bottom tab so the electronics tray can slide out.
    edge_gap = "assembly_clearance + lip_thickness + wall_thickness/2"
    tab_half_len_x = "body_width/2 - corner_radius - 2 mm"
    tab_half_len_z = "body_height/2 - corner_radius - 2 mm"
    tabs = [
        # (bridge centre, tab centre, half sizes for bridge, half sizes for tab)
        (dict(z="body_top_z - wall_thickness/2 - (%s)/2" % edge_gap),
         dict(z="body_top_z - wall_thickness - assembly_clearance - lip_thickness/2"),
         {"x": tab_half_len_x, "z": "(%s)/2" % edge_gap},
         {"x": tab_half_len_x, "z": "lip_thickness/2"}),
    ]
    for sign in (-1, 1):
        tabs.append((
            dict(x=side_expr(sign, "body_width/2 - wall_thickness/2 - (%s)/2" % edge_gap), z="body_center_z"),
            dict(x=side_expr(sign, "body_width/2 - wall_thickness - assembly_clearance - lip_thickness/2"),
                 z="body_center_z"),
            {"x": "(%s)/2" % edge_gap, "z": tab_half_len_z},
            {"x": "lip_thickness/2", "z": tab_half_len_z},
        ))
    bridges = r.sketch("y", "split_y", "Tab roots")
    lips = r.sketch("y", "split_y", "Locating tabs")
    for bridge_at, tab_at, bridge_half, tab_half in tabs:
        r.rect(bridges, r.project(bridges, r.anchor(**bridge_at)), bridge_half)
        r.rect(lips, r.project(lips, r.anchor(**tab_at)), tab_half)
    r.extrude(r.profiles(bridges), "lip_bridge_depth", Y_POS, JOIN, [r.body(name)], name="Tab roots")
    r.extrude(r.profiles(lips), "lip_depth", Y_NEG, JOIN, [r.body(name)], name="Locating tabs")

    # Vent slots: one seed slot, patterned along +X.
    sk = r.sketch("y", "body_depth/2 + 1 mm", "Rear vent seed")
    seed_x = "-(rear_vent_count - 1)*rear_vent_spacing/2"
    r.rect(sk, r.project(sk, r.anchor(x=seed_x, z="body_center_z")),
           {"x": "rear_vent_width/2", "z": "rear_vent_length/2"})
    vent = r.extrude(r.profiles(sk), "wall_thickness + 3 mm", Y_NEG, CUT, [r.body(name)], name="Rear vent")
    r.rect_pattern([vent], r.comp.xConstructionAxis, "rear_vent_count", "rear_vent_spacing", "Rear vent pattern")


def build_electronics_tray(t):
    name = "Electronics_Tray"
    sk = t.sketch("z", "tray_z", "Tray plate")
    t.rect(sk, t.project(sk, t.anchor()), {"x": "tray_width/2", "y": "tray_depth/2"})
    ext = t.extrude(t.profiles(sk), "tray_thickness", Z_POS, NEW, name="Tray plate")
    ext.bodies.item(0).name = name

    top = "tray_z + tray_thickness"
    sk = t.sketch("z", top, "Tray rails")
    for sign in (-1, 1):
        x = side_expr(sign, "tray_width/2 - tray_rail_width/2")
        t.rect(sk, t.project(sk, t.anchor(x=x)), {"x": "tray_rail_width/2", "y": "tray_depth/2"})
    t.extrude(t.profiles(sk), "tray_rail_height", Z_POS, JOIN, [t.body(name)], name="Tray rails")

    # Raspberry Pi 5 standoff: one seed, rectangular pattern 2 x 2.
    sk = t.sketch("z", top, "Standoff seed")
    c = t.project(sk, t.anchor(x="-pi_hole_spacing_x/2", y="-pi_hole_spacing_y/2"))
    t.circle(sk, c, "standoff_diameter")
    t.circle(sk, c, "standoff_hole_diameter")
    standoff = t.extrude(t.profiles(sk, loops=2), "standoff_height", Z_POS, JOIN, [t.body(name)], name="Standoff")
    t.rect_pattern([standoff], t.comp.xConstructionAxis, "2", "pi_hole_spacing_x", "Standoff pattern",
                   t.comp.yConstructionAxis, "2", "pi_hole_spacing_y")


# ---------------------------------------------------------------------------
# Stage F - appearances, joints, view
# ---------------------------------------------------------------------------

# name: (base appearance candidates, RGB)
APPEARANCES = {
    "AlfieBot Satin White": (["Plastic - Matte (White)", "Plastic - Glossy (White)"], (238, 238, 232)),
    "AlfieBot Black": (["Plastic - Matte (Black)", "Plastic - Glossy (Black)"], (22, 22, 24)),
    "AlfieBot Glossy Black": (["Plastic - Glossy (Black)", "Plastic - Matte (Black)"], (6, 6, 10)),
    "AlfieBot Dark Grey": (["Plastic - Matte (Gray)", "Plastic - Matte (Black)"], (62, 64, 68)),
    "AlfieBot Cyan Blue": (["Plastic - Glossy (Blue)", "Plastic - Matte (Blue)"], (0, 182, 235)),
    "AlfieBot Highlight White": (["Plastic - Glossy (White)", "Plastic - Matte (White)"], (255, 255, 255)),
}

# (component, body name or None for all bodies) -> appearance
APPEARANCE_MAP = [
    ("Main_Body", None, "AlfieBot Satin White"),
    ("Rear_Cover", None, "AlfieBot Satin White"),
    ("Front_Bezel", None, "AlfieBot Black"),
    ("Display_Placeholder", None, "AlfieBot Glossy Black"),
    ("Left_Speaker_Grille", None, "AlfieBot Dark Grey"),
    ("Right_Speaker_Grille", None, "AlfieBot Dark Grey"),
    ("Left_Accent_Ring", None, "AlfieBot Cyan Blue"),
    ("Right_Accent_Ring", None, "AlfieBot Cyan Blue"),
    ("Top_Button", "Button_Cap", "AlfieBot Dark Grey"),
    ("Top_Button", "Button_Accent", "AlfieBot Cyan Blue"),
    ("Feet", None, "AlfieBot Dark Grey"),
    ("Electronics_Tray", None, "AlfieBot Dark Grey"),
    ("Eye_Graphics", "Eye_Ring_1", "AlfieBot Cyan Blue"),
    ("Eye_Graphics", "Eye_Ring_2", "AlfieBot Cyan Blue"),
    ("Eye_Graphics", "Eye_Highlight_1", "AlfieBot Highlight White"),
    ("Eye_Graphics", "Eye_Highlight_2", "AlfieBot Highlight White"),
]


def _appearance_library():
    libraries = _app.materialLibraries
    for name in ("Fusion Appearance Library", "Fusion 360 Appearance Library"):
        try:
            lib = libraries.itemByName(name)
        except Exception:
            lib = None
        if lib:
            return lib
    for i in range(libraries.count):
        if "Appearance" in libraries.item(i).name:
            return libraries.item(i)
    return None


def _base_appearance(lib, candidates):
    for name in candidates:
        try:
            found = lib.appearances.itemByName(name)
        except Exception:
            found = None
        if found:
            return found
    for i in range(lib.appearances.count):
        if lib.appearances.item(i).name.startswith("Plastic"):
            return lib.appearances.item(i)
    return lib.appearances.item(0) if lib.appearances.count else None


def _tint(appearance, rgb):
    """Set the main colour property of a design appearance."""
    props = appearance.appearanceProperties
    for prop_id in ("opaque_albedo", "generic_diffuse"):
        prop = adsk.core.ColorProperty.cast(props.itemById(prop_id))
        if prop:
            prop.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
            return True
    for i in range(props.count):
        prop = adsk.core.ColorProperty.cast(props.item(i))
        if prop:
            prop.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
            return True
    return False


def apply_appearances(ctx):
    lib = _appearance_library()
    if not lib:
        log("No appearance library found; appearances skipped", "WARN")
        return
    design_appearances = ctx.design.appearances
    created = {}
    for name, (candidates, rgb) in APPEARANCES.items():
        existing = design_appearances.itemByName(name)
        if existing:
            created[name] = existing
            continue
        base = _base_appearance(lib, candidates)
        if not base:
            log("No base appearance for %s" % name, "WARN")
            continue
        appearance = design_appearances.addByCopy(base, name)
        if not _tint(appearance, rgb):
            log("Could not set colour on %s (base %s)" % (name, base.name), "WARN")
        created[name] = appearance
    for comp_name, body_name, appearance_name in APPEARANCE_MAP:
        b = ctx.builders.get(comp_name)
        appearance = created.get(appearance_name)
        if not b or not appearance:
            continue
        bodies = b.comp.bRepBodies
        for i in range(bodies.count):
            body = bodies.item(i)
            if body_name is None or body.name == body_name:
                body.appearance = appearance
    log("Appearances applied")


def create_joints(ctx):
    """Ground Main_Body; tie every other part to it with as-built rigid joints.

    Parts stay separate components, so any joint can be suppressed or
    deleted to move a part (e.g. the rear cover) independently.
    """
    main = ctx.b("Main_Body").occ
    main.isGrounded = True
    joints = ctx.asm.asBuiltJoints
    for name, b in ctx.builders.items():
        if name == "Main_Body":
            continue
        parent = ctx.b("Display_Placeholder").occ if name == "Eye_Graphics" else main
        try:
            joint_input = joints.createInput(parent, b.occ, None)
            joint_input.setAsRigidJointMotion()
            joint = joints.add(joint_input)
            joint.name = "Rigid %s" % name
        except Exception as exc:  # noqa: BLE001
            log("As-built joint for %s failed: %s" % (name, exc), "WARN")
    log("Main_Body grounded; as-built rigid joints created")


def set_view():
    """Z-up isometric-ish view from the front-left."""
    try:
        viewport = _app.activeViewport
        camera = viewport.camera
        camera.isSmoothTransition = False
        camera.target = point(0, 0, 7)
        camera.eye = point(-35, -60, 35)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        viewport.camera = camera
        viewport.fit()
    except Exception as exc:  # noqa: BLE001
        log("Could not set the view: %s" % exc, "WARN")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class Report:
    def __init__(self):
        self.rows = []

    def add(self, status, check, detail=""):
        self.rows.append((status, check, detail))
        log("%s: %s %s" % (check, status, detail), "CHECK")

    def count(self, status):
        return sum(1 for r in self.rows if r[0] == status)


def parameter_values_mm(design):
    values = {}
    for name, _expr, unit, _comment in AP.ALL_PARAMETERS:
        param = design.userParameters.itemByName(name)
        if param is None:
            continue
        values[name] = param.value * 10.0 if unit == "mm" else param.value
    return values


def tight_box_mm(bodies):
    """Union of per-body boxes along the assembly axes, in mm."""
    measure = _app.measureManager
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for body in bodies:
        try:
            obb = measure.getOrientedBoundingBox(body, adsk.core.Vector3D.create(1, 0, 0),
                                                 adsk.core.Vector3D.create(0, 1, 0))
            c = obb.centerPoint
            half = (obb.length / 2, obb.width / 2, obb.height / 2)
            mins = (c.x - half[0], c.y - half[1], c.z - half[2])
            maxs = (c.x + half[0], c.y + half[1], c.z + half[2])
        except Exception:
            bb = body.boundingBox
            mins = (bb.minPoint.x, bb.minPoint.y, bb.minPoint.z)
            maxs = (bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z)
        for i in range(3):
            lo[i] = min(lo[i], mins[i] * 10.0)
            hi[i] = max(hi[i], maxs[i] * 10.0)
    return tuple(zip(lo, hi))


def timeline_problems(design):
    problems = []
    try:
        timeline = design.timeline
    except Exception:
        return problems
    healthy = adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState
    for i in range(timeline.count):
        item = timeline.item(i)
        try:
            state = item.healthState
        except Exception:
            continue
        if state != healthy:
            problems.append("%s: %s" % (item.name, item.errorOrWarningMessage))
    return problems


def child_occurrences(ctx):
    """Child occurrences in assembly context (proxies), keyed by component name."""
    found = {}
    children = ctx.asm_occ.childOccurrences
    for i in range(children.count):
        occ = children.item(i)
        found[occ.component.name] = occ
    return found


def _entity_name(entity):
    occ = adsk.fusion.Occurrence.cast(entity)
    if occ:
        return occ.component.name
    body = adsk.fusion.BRepBody.cast(entity)
    if body:
        return "%s/%s" % (body.parentComponent.name, body.name)
    return str(entity)


def validate(ctx, report):
    design = ctx.design
    v = parameter_values_mm(design)
    occs = child_occurrences(ctx)

    # 1. Components exist
    missing = [n for n in AP.COMPONENTS if n not in occs]
    report.add("FAIL" if missing else "PASS", "All expected components exist",
               "missing: %s" % ", ".join(missing) if missing else "%d components" % len(AP.COMPONENTS))

    # 2. Valid solid bodies
    for name in AP.COMPONENTS + (AP.VISUAL_COMPONENTS if CREATE_EYE_GRAPHICS else []):
        occ = occs.get(name)
        if not occ:
            continue
        bodies = occ.component.bRepBodies
        bad = [bodies.item(i).name for i in range(bodies.count) if not bodies.item(i).isSolid]
        if bodies.count == 0:
            report.add("FAIL", "Solid bodies: %s" % name, "no bodies")
        elif bad:
            report.add("FAIL", "Solid bodies: %s" % name, "not solid: %s" % ", ".join(bad))
        else:
            report.add("PASS", "Solid bodies: %s" % name, "%d solid bod%s" % (bodies.count, "y" if bodies.count == 1 else "ies"))

    # 3. Main enclosure hollow
    main = occs.get("Main_Body")
    if main and main.component.bRepBodies.count:
        body = main.component.bRepBodies.item(0)
        envelope_cm3 = (v["body_width"] * v["body_height"] * (v["body_depth"] - v["rear_cover_depth"])) / 1000.0
        ratio = body.volume / envelope_cm3 if envelope_cm3 else 1
        centre = point(0, v["module_center_y"] / 10.0, v["body_center_z"] / 10.0)
        outside = body.pointContainment(centre) == adsk.fusion.PointContainment.PointOutsidePointContainment
        report.add("PASS" if (ratio < 0.35 and outside) else "FAIL", "Main enclosure is hollow",
                   "solid fraction %.2f, cavity centre empty: %s" % (ratio, outside))
        report.add("PASS" if body.lumps.count == 1 else "WARN", "Main_Body is one piece",
                   "%d lump(s)" % body.lumps.count)

    # 4. Overall envelope
    expected = AP.assembly_envelope(v)
    physical = [occs[n] for n in AP.COMPONENTS if n in occs]
    bodies = [occ.bRepBodies.item(i) for occ in physical for i in range(occ.bRepBodies.count)]
    if bodies:
        actual = tight_box_mm(bodies)
        worst = max(abs(a - e) for pair_a, pair_e in zip(actual, expected) for a, e in zip(pair_a, pair_e))
        report.add("PASS" if worst <= 1.0 else "WARN", "Overall envelope",
                   "actual %.1f x %.1f x %.1f mm, expected %.1f x %.1f x %.1f mm" % (
                       AP.box_size(actual) + AP.box_size(expected)))

    # 5. Build volume per printable component
    for name in AP.PRINTABLE_COMPONENTS:
        occ = occs.get(name)
        if not occ or occ.bRepBodies.count == 0:
            continue
        box = tight_box_mm([occ.bRepBodies.item(i) for i in range(occ.bRepBodies.count)])
        size = AP.box_size(box)
        report.add("PASS" if AP.fits_build_volume(size) else "FAIL", "Fits A1 Mini: %s" % name,
                   "%.1f x %.1f x %.1f mm" % size)

    # 6. Interference
    try:
        interference_input = design.createInterferenceInput(collection(physical))
        interference_input.areCoincidentFacesIncluded = False
        results = design.analyzeInterference(interference_input)
        clashes = []
        for i in range(results.count):
            res = results.item(i)
            vol_mm3 = res.interferenceBody.volume * 1000.0
            if vol_mm3 > 0.001:
                clashes.append("%s x %s (%.3f mm3)" % (_entity_name(res.entityOne), _entity_name(res.entityTwo), vol_mm3))
        report.add("FAIL" if clashes else "PASS", "No unintended intersections",
                   "; ".join(clashes) if clashes else "no interference between %d components" % len(physical))
    except Exception as exc:  # noqa: BLE001
        report.add("WARN", "No unintended intersections", "interference analysis failed: %s" % exc)

    # 7. Rear cover and bezel separate
    for name in ("Rear_Cover", "Front_Bezel"):
        occ = occs.get(name)
        count = occ.component.bRepBodies.count if occ else 0
        ok = count >= 1 and (main is None or occ.component != main.component)
        report.add("PASS" if ok else "FAIL", "%s is a separate component" % name,
                   "own component with %d body(ies)" % count)

    # 8. Analytic design rules on the live parameter values
    for status, check, detail in AP.design_rule_checks(v):
        if not check.startswith("Fits A1 Mini"):  # measured above
            report.add(status, "Rule: " + check, detail)

    # 9. Timeline health
    problems = timeline_problems(design)
    report.add("FAIL" if problems else "PASS", "Timeline health",
               "; ".join(problems[:10]) if problems else "all features healthy")


def flex_test(ctx, report):
    """Edit parameters one at a time, check the timeline recomputes, then restore."""
    design = ctx.design
    user_params = design.userParameters
    for name, test_expression in AP.FLEX_TESTS:
        param = user_params.itemByName(name)
        if not param:
            continue
        original = param.expression
        try:
            param.expression = test_expression
            adsk.doEvents()
            problems = timeline_problems(design)
            empty = [n for n, b in ctx.builders.items() if b.comp.bRepBodies.count == 0]
            ok = not problems and not empty
            issues = problems[:5] + (["empty components: %s" % ", ".join(empty)] if empty else [])
            detail = "OK" if ok else "; ".join(issues)
            report.add("PASS" if ok else "FAIL", "Parameter edit %s = %s" % (name, test_expression), detail)
        except Exception as exc:  # noqa: BLE001
            report.add("FAIL", "Parameter edit %s = %s" % (name, test_expression), str(exc))
        finally:
            param.expression = original
            adsk.doEvents()
    problems = timeline_problems(design)
    report.add("FAIL" if problems else "PASS", "Model restored after parameter edits",
               "; ".join(problems[:5]) if problems else "all features healthy")


def write_report(report, elapsed):
    lines = [
        "AlfieBot V%s - Fusion validation report" % AP.VERSION,
        "Generated: %s   Build time: %.1f s" % (time.strftime("%Y-%m-%d %H:%M:%S"), elapsed),
        "",
        "Summary: %d PASS, %d WARN, %d FAIL" % (report.count("PASS"), report.count("WARN"), report.count("FAIL")),
        "",
    ]
    for status, check, detail in report.rows:
        lines.append("[%s] %s - %s" % (status, check, detail))
    lines += ["", "Build log:"] + _log_lines
    text = "\n".join(lines)
    for folder in (_SCRIPT_DIR, os.path.expanduser("~")):
        path = os.path.join(folder, REPORT_FILE_NAME)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            return path
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def create_user_parameters(design):
    user_params = design.userParameters
    for name, expression, unit, comment in AP.ALL_PARAMETERS:
        existing = user_params.itemByName(name)
        if existing:
            existing.expression = expression
            existing.comment = comment
        else:
            user_params.add(name, vi(expression), unit, comment)
    log("Created %d user parameters" % len(AP.ALL_PARAMETERS))


def prepare_design():
    if CREATE_NEW_DOCUMENT:
        doc = _app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        try:
            doc.name = AP.ASSEMBLY_NAME
        except Exception:
            pass
    design = adsk.fusion.Design.cast(_app.activeProduct)
    if not design:
        raise StageError("No active Fusion design. Open the Design workspace and run again.")
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    return design


STAGES = [
    ("A", "Main rounded body", stage_a_main_body),
    ("B", "Front face, bezel and display", stage_b_front),
    ("C", "Speaker grilles and accent rings", stage_c_speakers),
    ("D", "Top button and feet", stage_d_button_feet),
    ("E", "Rear cover and electronics tray", stage_e_rear_tray),
]


def run(context):
    global _app, _ui
    _log_lines.clear()
    started = time.time()
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        log("AlfieBot V%s generator starting" % AP.VERSION)

        design = prepare_design()
        create_user_parameters(design)

        root = design.rootComponent
        assembly_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        assembly_occ.component.name = AP.ASSEMBLY_NAME
        ctx = BuildContext(design, assembly_occ)
        for name in AP.COMPONENTS + (AP.VISUAL_COMPONENTS if CREATE_EYE_GRAPHICS else []):
            ctx.add_component(name)
        log("Created %d components under %s" % (len(ctx.builders), AP.ASSEMBLY_NAME))

        # Each stage is isolated: a failure is logged and later stages still run.
        for code, title, func in STAGES:
            try:
                func(ctx)
                ctx.stage_status.append((code, title, "OK", ""))
                log("Stage %s (%s) complete" % (code, title))
            except Exception as exc:  # noqa: BLE001
                ctx.stage_status.append((code, title, "FAILED", str(exc)))
                log("Stage %s (%s) FAILED: %s\n%s" % (code, title, exc, traceback.format_exc()), "ERROR")
            adsk.doEvents()

        # Stage F
        for label, func in (("Appearances", apply_appearances if APPLY_APPEARANCES else None),
                            ("Joints", create_joints if CREATE_JOINTS else None)):
            if func is None:
                continue
            try:
                func(ctx)
            except Exception as exc:  # noqa: BLE001
                log("%s failed: %s\n%s" % (label, exc, traceback.format_exc()), "ERROR")
        set_view()

        report = Report()
        for code, title, status, detail in ctx.stage_status:
            report.add("PASS" if status == "OK" else "FAIL", "Stage %s: %s" % (code, title), detail)
        if RUN_VALIDATION:
            try:
                validate(ctx, report)
            except Exception as exc:  # noqa: BLE001
                report.add("FAIL", "Validation", "%s\n%s" % (exc, traceback.format_exc()))
        if RUN_PARAMETER_FLEX_TEST:
            try:
                flex_test(ctx, report)
            except Exception as exc:  # noqa: BLE001
                report.add("FAIL", "Parameter flex test", str(exc))

        path = write_report(report, time.time() - started)
        failures = [r for r in report.rows if r[0] == "FAIL"]
        summary = "AlfieBot V%s generated.\n\n%d PASS, %d WARN, %d FAIL\n" % (
            AP.VERSION, report.count("PASS"), report.count("WARN"), report.count("FAIL"))
        if failures:
            summary += "\nFailures:\n" + "\n".join("- %s: %s" % (r[1], r[2][:160]) for r in failures[:8])
        summary += "\n\nFull report: %s" % (path or "(could not write report file)")
        _ui.messageBox(summary, "AlfieBot Generator")
    except Exception:  # noqa: BLE001
        message = "AlfieBot generator failed:\n%s" % traceback.format_exc()
        log(message, "ERROR")
        if _ui:
            _ui.messageBox(message, "AlfieBot Generator")
