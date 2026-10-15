import cv2 as cv
import os
import json
import numpy as np

path = os.path.expanduser(
    "~/Project/Rob7_Gr760_P7/Map/MapFiles/Map1/jueying.pgm"
)

map_img = cv.imread(path, cv.IMREAD_GRAYSCALE)

if map_img is None:
    raise FileNotFoundError(f"Could not load map: {path}")

original = cv.cvtColor(map_img, cv.COLOR_GRAY2BGR)

# Waypoints are stored in original map pixel coordinates
waypoints = []

window_name = "Waypoint editor"
max_width = 1000
max_height = 800

# Scale the map to fit the display without changing its coordinates
map_height, map_width = map_img.shape
scale = min(
    max_width / map_width,
    max_height / map_height,
    1.0
)

display_width = int(map_width * scale)
display_height = int(map_height * scale)

frame = original.copy()


def update_display():
    global frame

    frame = original.copy()

    for i, wp in enumerate(waypoints):
        x, y = wp["x"], wp["y"]

        # Draw waypoint marker
        cv.circle(frame, (x, y), 6, (0, 0, 255), -1)
        cv.circle(frame, (x, y), 9, (255, 255, 255), 2)

        # Draw waypoint number
        cv.putText(
            frame, str(i + 1), (x + 10, y - 10),
            cv.FONT_HERSHEY_SIMPLEX, 0.6,
            (0, 0, 255), 2
        )

        # Draw waypoint name if assigned
        if wp["name"]:
            cv.putText(
                frame, wp["name"], (x + 10, y + 15),
                cv.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 0, 0), 1
            )

    # Resize only the displayed image, not the stored map
    display = cv.resize(
        frame,
        (display_width, display_height),
        interpolation=cv.INTER_AREA
    )

    cv.imshow(window_name, display)


def mouse_callback(event, x, y, flags, param):
    if event == cv.EVENT_LBUTTONDOWN:
        # Convert display coordinates to original map coordinates
        map_x = round(x / scale)
        map_y = round(y / scale)

        # Keep coordinates inside the map
        map_x = max(0, min(map_x, map_width - 1))
        map_y = max(0, min(map_y, map_height - 1))

        waypoints.append({
            "x": map_x,
            "y": map_y,
            "name": "",
            "descriptor": ""
        })

        print(
            f"Waypoint {len(waypoints)} placed at "
            f"({map_x}, {map_y})"
        )

        update_display()


# # cv.namedWindow(window_name, cv.WINDOW_AUTOSIZE)
# # cv.setMouseCallback(window_name, mouse_callback)

# Create the window only once
cv.namedWindow(window_name, cv.WINDOW_NORMAL)

# Set a fixed window size
cv.resizeWindow(window_name, 800, 600)

# Register the mouse callback
cv.setMouseCallback(window_name, mouse_callback)

update_display()

print("\nWaypoint editor")
print("Left-click: place waypoint")
print("Backspace: undo last waypoint")
print("R: clear all waypoints")
print("ESC: finish and name waypoints")

while True:
    key = cv.waitKey(20) & 0xFF

    if key == 27:  # ESC
        break

    elif key == ord("r"):
        waypoints.clear()
        update_display()
        print("All waypoints cleared.")

    elif key == 8 or key == 127:  # Backspace
        if waypoints:
            removed = waypoints.pop()
            print(f"Removed waypoint at ({removed['x']}, {removed['y']})")
            update_display()



# Assign names and descriptors after placing the waypoints
for i, wp in enumerate(waypoints):
    print(f"\nWaypoint {i + 1} at ({wp['x']}, {wp['y']})")

    wp["name"] = input("Name: ").strip()
    wp["descriptor"] = input("Descriptor: ").strip()

# Print and save waypoint data
output_path = os.path.join(
    os.path.dirname(path),
    "waypoints.json"
)
cv.destroyAllWindows()

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(waypoints, f, indent=4, ensure_ascii=False)

print("\nFinal waypoints:")
print(json.dumps(waypoints, indent=4, ensure_ascii=False))
print(f"\nSaved to: {output_path}")

# Show the final annotated map
update_display()
cv.imshow("Final Waypoints", cv.resize(
    frame, (display_width, display_height),
    interpolation=cv.INTER_AREA
))
cv.waitKey(0)
cv.destroyAllWindows()
