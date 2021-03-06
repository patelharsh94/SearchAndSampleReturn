import numpy as np
import cv2
from preception_support import *

# Define a function to convert from image coords to rover coords
def rover_coords(binary_img):
    # Identify nonzero pixels
    ypos, xpos = binary_img.nonzero()
    # Calculate pixel positions with reference to the rover position being at the 
    # center bottom of the image.  
    x_pixel = -(ypos - binary_img.shape[0]).astype(np.float)
    y_pixel = -(xpos - binary_img.shape[1]/2 ).astype(np.float)
    return x_pixel, y_pixel


# Define a function to convert to radial coords in rover space
def to_polar_coords(x_pixel, y_pixel):
    # Convert (x_pixel, y_pixel) to (distance, angle) 
    # in polar coordinates in rover space
    # Calculate distance to each pixel
    dist = np.sqrt(x_pixel**2 + y_pixel**2)
    # Calculate angle away from vertical for each pixel
    angles = np.arctan2(y_pixel, x_pixel)

    #mean_angles = np.mean(angles)
    return dist, angles

# Define a function to map rover space pixels to world space
def rotate_pix(xpix, ypix, yaw):
    # Convert yaw to radians
    yaw_rad = yaw * np.pi / 180
    xpix_rotated = (xpix * np.cos(yaw_rad)) - (ypix * np.sin(yaw_rad))
                            
    ypix_rotated = (xpix * np.sin(yaw_rad)) + (ypix * np.cos(yaw_rad))
    # Return the result  
    return xpix_rotated, ypix_rotated

def translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale): 
    # Apply a scaling and a translation
    xpix_translated = (xpix_rot / scale) + xpos
    ypix_translated = (ypix_rot / scale) + ypos
    # Return the result  
    return xpix_translated, ypix_translated


# Define a function to apply rotation and translation (and clipping)
# Once you define the two functions above this function should work
def pix_to_world(xpix, ypix, xpos, ypos, yaw, world_size, scale):
    # Apply rotation
    xpix_rot, ypix_rot = rotate_pix(xpix, ypix, yaw)
    # Apply translation
    xpix_tran, ypix_tran = translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale)
    # Perform rotation, translation and clipping all at once
    x_pix_world = np.clip(np.int_(xpix_tran), 0, world_size - 1)
    y_pix_world = np.clip(np.int_(ypix_tran), 0, world_size - 1)
    # Return the result
    return x_pix_world, y_pix_world

# Define a function to perform a perspective transform
def perspect_transform(img, src, dst):
           
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (img.shape[1], img.shape[0]))# keep same size as input image
    
    return warped


# Apply the above functions in succession and update the Rover state accordingly
def perception_step(Rover):
    # Perform perception steps to update Rover()
    # TODO: 
    # NOTE: camera image is coming to you in Rover.img
    # 1) Define source and destination points for perspective transform
    # 2) Apply perspective transform
    # 3) Apply color threshold to identify navigable terrain/obstacles/rock samples
    # 4) Update Rover.vision_image (this will be displayed on left side of screen)
        # Example: Rover.vision_image[:,:,0] = obstacle color-thresholded binary image
        #          Rover.vision_image[:,:,1] = rock_sample color-thresholded binary image
        #          Rover.vision_image[:,:,2] = navigable terrain color-thresholded binary image

    # 5) Convert map image pixel values to rover-centric coords
    # 6) Convert rover-centric pixel values to world coordinates
    # 7) Update Rover worldmap (to be displayed on right side of screen)
        # Example: Rover.worldmap[obstacle_y_world, obstacle_x_world, 0] += 1
        #          Rover.worldmap[rock_y_world, rock_x_world, 1] += 1
        #          Rover.worldmap[navigable_y_world, navigable_x_world, 2] += 1

    # 8) Convert rover-centric pixel positions to polar coordinates
    # Update Rover pixel distances and angles
        # Rover.nav_dists = rover_centric_pixel_distances
        # Rover.nav_angles = rover_centric_angles
    
    dst_size = 15
    bottom_offset = 6
    image = Rover.img
    
    source = np.float32([[14, 140], [301 ,140],[200, 96], [118, 96]])
    destination = np.float32([[image.shape[1]/2 - dst_size, image.shape[0] - bottom_offset],
                  [image.shape[1]/2 + dst_size, image.shape[0] - bottom_offset],
                  [image.shape[1]/2 + dst_size, image.shape[0] - 2*dst_size - bottom_offset], 
                  [image.shape[1]/2 - dst_size, image.shape[0] - 2*dst_size - bottom_offset],
                  ])


    warped = perspect_transform(image, source, destination)
    
    # 3)
    navigable_img = color_thresh(warped)
    obstacle_img, rock_img = find_obstacles_and_rocks(warped)
    
    # multiply by 255 so 1 = 255 and we can see it
    Rover.vision_image[:,:,2] = navigable_img * 255
    Rover.vision_image[:,:,0] = obstacle_img * 255

    # 4)
    obs_xPix, obs_yPix = rover_coords(obstacle_img)
    xPix, yPix = rover_coords(navigable_img)
    
    # 5)
    world_size = Rover.worldmap.shape[0]
    scale = 2 * dst_size
    obs_x_world, obs_y_world = pix_to_world(obs_xPix, obs_yPix,      
                                            Rover.pos[0], Rover.pos[1], 
                                            Rover.yaw, world_size,
                                            scale)
    navigable_x_world, navigable_y_world = pix_to_world(xPix,yPix, Rover.pos[0], Rover.pos[1],
                                                       Rover.yaw, world_size,
                                                       scale)
    # 6)
    Rover.worldmap[obs_y_world, obs_x_world, 0] += 1
    Rover.worldmap[navigable_y_world, navigable_x_world, 2] += 10
    nav_pix = Rover.worldmap[:,:,2] > 0 # Navigatable pixels are the one in the 2 channel
    Rover.worldmap[nav_pix, 0] = 0  # basically creating a mask so we don't overlap
    
    dist, angles = to_polar_coords(xPix, yPix)
    Rover.nav_angles = angles
    rock_px_count = np.count_nonzero(rock_img==1)
    
    if rock_px_count > 290 and rock_px_count < 330:
        print("FOUND ROCK")
        Rover.rock_nearby = True
        rock_xPix, rock_yPix = rover_coords(rock_img)
        rock_x_world, rock_y_world = pix_to_world(rock_xPix, rock_yPix, 
                                                Rover.pos[0], Rover.pos[1], 
                                                Rover.yaw, world_size,
                                                scale)
        rock_distance, rock_angle = to_polar_coords(rock_xPix, rock_yPix)
        # Take the min dist rock pix, and call it the center point
        # then update the rover world map
        rock_idx = np.argmin(rock_distance)
        rock_xcen = rock_x_world[rock_idx]
        rock_ycen = rock_y_world[rock_idx]
        Rover.nav_angles = rock_angle
        Rover.worldmap[rock_ycen, rock_xcen, 1] = 255
        Rover.vision_image[:,:,1] = rock_img * 255
    else:
        Rover.vision_image[:,:,1] = 0
        
    Rover.near_sample = False    
    
    return Rover