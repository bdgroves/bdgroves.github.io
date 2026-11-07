import numpy as np
def project(P, cam, W, H):
    """World points (N,3) -> pixel x,y and view depth, matching forge3d's pinhole camera."""
    o=np.array(cam["origin"],float); t=np.array(cam["look_at"],float); up=np.array(cam["up"],float)
    fwd=t-o; fwd/=np.linalg.norm(fwd)
    right=np.cross(fwd,up); right/=np.linalg.norm(right)
    u=np.cross(right,fwd)
    v=np.asarray(P,float)-o
    x=v@right; y=v@u; z=v@fwd
    th=np.tan(np.radians(cam["fov_y"])/2); asp=cam.get("aspect",W/H)
    px=(x/(z*th*asp)*0.5+0.5)*W; py=(0.5-y/(z*th)*0.5)*H
    dist=np.linalg.norm(v,axis=1)
    return px,py,z,dist
