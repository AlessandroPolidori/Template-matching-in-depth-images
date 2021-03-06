import cv2
import numpy as np
import getopt
import sys
import random
#from sklearn.neighbours import KDTree
from scipy.spatial import KDTree

from sympy import *
from mpmath import mp

#
# Computers a homography from 4-correspondences
#
def calculateHomography(correspondences):
    #loop through correspondences and create assemble matrix
    aList = []
    for corr in correspondences:
        p1 = np.matrix([corr.item(0), corr.item(1), 1])
        p2 = np.matrix([corr.item(2), corr.item(3), 1])

        a2 = [0, 0, 0, -p2.item(2) * p1.item(0), -p2.item(2) * p1.item(1), -p2.item(2) * p1.item(2),
              p2.item(1) * p1.item(0), p2.item(1) * p1.item(1), p2.item(1) * p1.item(2)]
        a1 = [-p2.item(2) * p1.item(0), -p2.item(2) * p1.item(1), -p2.item(2) * p1.item(2), 0, 0, 0,
              p2.item(0) * p1.item(0), p2.item(0) * p1.item(1), p2.item(0) * p1.item(2)]
        aList.append(a1)
        aList.append(a2)

    matrixA = np.matrix(aList)

    #svd composition
    u, s, v = np.linalg.svd(matrixA)

    #reshape the min singular value into a 3 by 3 matrix
    h = np.reshape(v[8], (3, 3))

    #normalize and now we have h
    h = (1/h.item(8)) * h
    return h
#
#Calculate the geometric distance between estimated points and original points
#
def geometricDistance(correspondence, h):

    p1 = np.transpose(np.matrix([correspondence[0].item(0), correspondence[0].item(1), 1]))
    estimatep2 = np.dot(h, p1)
    if (estimatep2.item(2) != 0):
        estimatep2 = (1/estimatep2.item(2))*estimatep2
    else:
        return 1000
    p2 = np.transpose(np.matrix([correspondence[0].item(2), correspondence[0].item(3), 1]))
    error = p2 - estimatep2
    return np.linalg.norm(error)
#
#Runs through ransac algorithm, creating homographies from random correspondences
#
def customFindHomography(obj,scene, thresh):

    random.seed(1234)
    
    correspondenceList = []

    for z in range(len(scene[:,0])):
            (x1, y1) = obj[z,0] , obj[z,1]
            (x2, y2) = scene[z,0] , scene[z,1]
            correspondenceList.append([x1, y1, x2, y2])

    corr = np.matrix(correspondenceList)

    maxInliers = []
    finalH = None
    finalMask = np.zeros(shape = (len(obj[:,0])) )
    for i in range(300):

        mask = np.zeros(shape = (len(obj[:,0])) )

        #find 4 random points to calculate a homography
        corr1 = corr[random.randrange(0, len(corr))]
        corr2 = corr[random.randrange(0, len(corr))]
        randomFour = np.vstack((corr1, corr2))
        corr3 = corr[random.randrange(0, len(corr))]
        randomFour = np.vstack((randomFour, corr3))
        corr4 = corr[random.randrange(0, len(corr))]
        randomFour = np.vstack((randomFour, corr4))

        #call the homography function on those points
        h = calculateHomography(randomFour)
        inliers = []
        

        for i in range(len(corr)):
            d = geometricDistance(corr[i], h)
            if d < 4:
                inliers.append(corr[i])
                mask[i] = 1
                

        if len(inliers) > len(maxInliers):
            
            maxInliers = inliers
            finalH = h
            finalMask = mask

        #print ("Corr size: ", len(corr), " NumInliers: ", len(inliers), "Max inliers: ", len(maxInliers))

        if len(maxInliers) > (len(corr)*thresh):
            
            break

    return finalH, finalMask;
#
#Finds plane through 3 points
#
def planeThroughPoints(p1, p2, p3):
    # These two vectors are in the plane
    v1 = p3 - p1
    v2 = p2 - p1

    # the cross product is a vector normal to the plane
    cp = np.cross(v1, v2)
    a, b, c = cp

    # This evaluates a * x3 + b * y3 + c * z3 which equals -d
    d = - np.dot(cp, p3)
    plane_normal = cp
    plane = [a, b, c, d]

    return plane_normal, plane
#
#Finds plane-point distance
#
def pointPlaneDistance(plane, point):
    a = plane[0]
    b = plane[1]
    c = plane[2]
    d = plane[3]
    x0 = point[0]
    y0 = point[1]
    z0 = point[2]
    return np.abs(a*x0 + b*y0 + c*z0 + d) / np.sqrt(a**2 + b**2 + c**2)
#
#Find Homography checking if the 4 scene points are co-planar first
#
def customFindHomographyPlane3D(obj, scene, point_cloud, thresh):

    random.seed(1234)
    
    plane_error = 0.01

    correspondenceList = []

    for z in range(len(scene[:,0])):
            (x1, y1) = obj[z,0] , obj[z,1]
            (x2, y2) = scene[z,0] , scene[z,1]
            correspondenceList.append([x1, y1, x2, y2])

    corr = np.matrix(correspondenceList)

    maxInliers = []
    finalH = None
    finalMask = np.zeros(shape = (len(obj[:,0])) )
    for i in range(300):

        mask = np.zeros(shape = (len(obj[:,0])) )

        #find 4 random co-planar points to calculate a homography
        point_on_plane = False
        while(not point_on_plane):
            corr1 = corr[random.randrange(0, len(corr))]
            corr2 = corr[random.randrange(0, len(corr))]
            randomFour = np.vstack((corr1, corr2))
            corr3 = corr[random.randrange(0, len(corr))]
            randomFour = np.vstack((randomFour, corr3))
            corr4 = corr[random.randrange(0, len(corr))]
            randomFour = np.vstack((randomFour, corr4))

            plane_normal, plane = planeThroughPoints(point_cloud[int(corr1[0, 3]), int(corr1[0, 2])],
                point_cloud[int(corr2[0, 3]), int(corr2[0, 2])], 
                point_cloud[int(corr3[0, 3]), int(corr3[0, 2])])

            point4 = point_cloud[int(corr4[0, 3]), int(corr4[0, 2])]
            distance = pointPlaneDistance(plane, point4)
            if(distance < plane_error):
                point_on_plane = True;
                #print("################################Plane found#####################################")
            #else:
                #print("------------------------------------------------------Plane not found----------------------------------------------------------")

        #call the homography function on those points
        h = calculateHomography(randomFour)
        inliers = []
        

        for i in range(len(corr)):
            d = geometricDistance(corr[i], h)
            if d < 4:
                inliers.append(corr[i])
                mask[i] = 1
                

        if len(inliers) > len(maxInliers):
            
            maxInliers = inliers
            finalH = h
            finalMask = mask

        #print ("Corr size: ", len(corr), " NumInliers: ", len(inliers), "Max inliers: ", len(maxInliers))

        if len(maxInliers) > (len(corr)*thresh):
            break

    return finalH, finalMask;

#
#returns the distance between the centralPoint and the 3d position of the correspondence's scene feature
#
def distance3D(corr, point_sampled, point_cloud):
    p0 = point_cloud[int(corr[0, 3]), int(corr[0, 2])]
    d = np.linalg.norm(point_sampled-p0)
    return d;
#
#returning max distance and index of the max-distance element
#
def findMin(corr, point_sampled, point_cloud):
    
    min = 10000
    minCorr = corr[0];
    for c in corr:
        d = distance3D(c, point_sampled, point_cloud)
        if (d < min):
            min = d
            minCorr = c
    return minCorr;
#
#Correspondances are sampled based on the 3D position of the scene features. First one is totally random, while the other 3 are sampled
#through normal distributions on x,y,z. A random 3D point is sampled and then the 3 closest features on scene are found.
#
def normalSampling3D(corr, point_cloud, std_dev):

    #sampling with a uniform distribution the first match
    corr1 = corr[random.randrange(0, len(corr))]
    #taking the 3D position of the scene feature
    firstPoint = point_cloud[int(corr1[0, 3]), int(corr1[0, 2])]
    minCorr = []
    for i in range(3):
        #sampling with normal distributions a point in space
        x_sampled = np.random.normal(firstPoint[0],std_dev)
        y_sampled = np.random.normal(firstPoint[1],std_dev)
        z_sampled = np.random.normal(firstPoint[2],std_dev)
        point_sampled = [x_sampled,y_sampled,z_sampled]
    
        #find the corr with min distance from point_sampled
        minCorr.append(findMin(corr, point_sampled,point_cloud))
        
    

    #Time Complexity: O((n-k)*k)

    #corr1 + minDistanceThree are the 4 correspondances to return
    corr2 = minCorr[0]
    randomFour = np.vstack((corr1, corr2))
    corr3 = minCorr[1]
    randomFour = np.vstack((randomFour, corr3))
    corr4 = minCorr[2]
    randomFour = np.vstack((randomFour, corr4))

    return randomFour;

def customFindHomographyNormalSampling3D(obj, scene, point_cloud, thresh, std_dev):

    random.seed(1234)

    correspondenceList = []

    for z in range(len(scene[:,0])):
            (x1, y1) = obj[z,0] , obj[z,1]
            (x2, y2) = scene[z,0] , scene[z,1]
            correspondenceList.append([x1, y1, x2, y2])

    corr = np.matrix(correspondenceList)

    maxInliers = []
    finalH = None
    finalMask = np.zeros(shape = (len(obj[:,0])) )
    for i in range(300):
        
        mask = np.zeros(shape = (len(obj[:,0])) )

        randomFour = normalSampling3D(corr, point_cloud, std_dev)

        #call the homography function on those points
        h = calculateHomography(randomFour)
        inliers = []
        

        for i in range(len(corr)):
            d = geometricDistance(corr[i], h)
            if d < 4:
                inliers.append(corr[i])
                mask[i] = 1
                

        if len(inliers) > len(maxInliers):
            
            maxInliers = inliers
            finalH = h
            finalMask = mask

        #print ("Corr size: ", len(corr), " NumInliers: ", len(inliers), "Max inliers: ", len(maxInliers))

        if len(maxInliers) > (len(corr)*thresh):
            
            break

        
    return finalH, finalMask;

def buildKDTree(obj, scene, point_cloud):
    correspondenceList = []

    for z in range(len(scene[:,0])):
            (x1, y1) = obj[z,0] , obj[z,1]
            (x2, y2) = scene[z,0] , scene[z,1]
            correspondenceList.append([x1, y1, x2, y2])

    corr = np.matrix(correspondenceList)

    #build tree
    X = []
    for i in range(len(corr)):
        X.append(point_cloud[int(corr[i, 3]), int(corr[i, 2])])
    X = np.matrix(X)
    tree = KDTree(X, leafsize = 2)

    return tree, corr

#
#randomly sample the other 3 points in a certain 3d-tree region containing the closest points
#
def sampling3DTree(corr, point_cloud, tree):
    #sampling with a uniform distribution the first match
    corr1 = corr[random.randrange(0, len(corr))]
    #taking the 3D position of the scene feature
    firstPoint = point_cloud[int(corr1[0, 3]), int(corr1[0, 2])]

    #find the k corrs with min distance from point_sampled
    dist, ind = tree.query(np.asarray(firstPoint).reshape((1, -1)), k=20)

    #random points
    ind = random.sample(list(ind[0]), 3)

    corr2 = corr[ind[0]]
    randomFour = np.vstack((corr1, corr2))
    corr3 = corr[ind[1]]
    randomFour = np.vstack((randomFour, corr3))
    corr4 = corr[ind[2]]
    randomFour = np.vstack((randomFour, corr4))

    return randomFour

#https://math.stackexchange.com/questions/3509039/calculate-homography-with-and-without-svd
def homographyEstimateSVD(points):
    mat = []
    for p in points:

        x_1 = [p[0, 0], p[0, 1]]
        y_1 = [p[0, 2], p[0, 3]]
        row1 = [x_1[0]*-1 ,y_1[0]*-1 ,-1 ,0 ,0 ,0 ,x_1[0]*x_1[1] ,y_1[0]*x_1[1] ,x_1[1]]
        row2 = [0 ,0 ,0 ,x_1[0]*-1 , y_1[0]*-1 ,-1 ,x_1[0]*y_1[1] ,y_1[0]*y_1[1] ,y_1[1]]
        mat.append(row1)
        mat.append(row2)

    P = np.matrix(mat)
    [U, S, Vt] = np.linalg.svd(P)
    homography = Vt[-1].reshape(3, 3)
    
    return homography

#
#Find Homography, sampling is not uniform but based on 3D distance of scene features. Sampling of the first match is random, then
#sampling of the other 3 points is based on a kd tree built using the 3 spatial dimensions
#
def customFindHomography3DTree(obj, scene, point_cloud, thresh):

    random.seed(1234)

    #print("Building Tree")
    #build KDTree between points in the 3d scene
    tree, corr = buildKDTree(obj, scene, point_cloud)

    maxInliers = []
    finalH = None
    finalMask = np.zeros(shape = (len(obj[:,0])) )
    for i in range(300):
        
        mask = np.zeros(shape = (len(obj[:,0])) )

        randomFour = sampling3DTree(corr, point_cloud, tree)

        #call the homography function on those points
        h = calculateHomography(randomFour)
        inliers = []
        

        for i in range(len(corr)):
            d = geometricDistance(corr[i], h)
            if d < 4:
                inliers.append(corr[i])
                mask[i] = 1
                

        if len(inliers) > len(maxInliers):
            
            maxInliers = inliers
            finalH = h
            finalMask = mask

        #print ("Corr size: ", len(corr), " NumInliers: ", len(inliers), "Max inliers: ", len(maxInliers))

        if len(maxInliers) > (len(corr)*thresh):
            
            break

    ### VALIDATION
    #estimatedHomography = homographyEstimateSVD(maxInliers)
    #finalInliers = []
    #finalMask = np.zeros(shape = (len(obj[:,0])) )
#
    #for i in range(len(corr)):
    #    d = geometricDistance(corr[i], h)
    #    if d < 3:
    #        finalInliers.append(corr[i])
    #        finalMask[i] = 1
        
    return finalH, finalMask;


