#!/bin/bash

# Create the needed lvm objects so we can then use the dbus service and
# introspection data to create the API documentation.

function _g
{
    echo "executing: $@"
    eval "$@"
    local rc=$?
    if [ ${rc} -ne 0 ]; then
        # We don't do clean on error in case we need to investigate.
       	vgremove -f doc_vg
        exit 1
    fi
}

# Create a VG
_g vgcreate doc_vg /dev/sdb /dev/sdc /dev/sdd /dev/sde

# Create a plain linear LV
_g lvcreate -L4m doc_vg

# Create an old style snapshot
_g lvcreate --size 4m --snapshot --name old_snap doc_vg/lvol0

# Create a thin pool
_g lvcreate -T -L512M --name thin_pool doc_vg

# Create a Cache pool
_g lvcreate -L8m -n lv_cache_meta doc_vg
_g lvcreate -L16m -n lv_cache doc_vg
_g lvconvert -y --type cache-pool --poolmetadata doc_vg/lv_cache_meta doc_vg/lv_cache
  
# Create another Cache pool
_g lvcreate -L8M -n lv_cache_meta doc_vg
_g lvcreate -L16m -n lv_cache_too  doc_vg
_g lvconvert -y --type cache-pool --poolmetadata doc_vg/lv_cache_meta doc_vg/lv_cache_too

# Create a thin LV
_g lvcreate -V 16M -T doc_vg/thin_pool -n thin_lv

# Snapshot the thin LV
_g lvcreate --snapshot --name thin_lv_snap doc_vg/thin_lv
 

# Create some LV to cache from cache pool
_g lvcreate -L128M -n lv_to_cache doc_vg

# Cache the LV
_g lvconvert -y --type cache --cachepool doc_vg/lv_cache doc_vg/lv_to_cache

echo "Create a job using the dbus interface and then run ./doc_gen.py > api.md"
 
# NOTE: Need to generate a job to have a job object, at the moment just
# create a simple linear LV in d-feet

# When ready
# ./doc_gen.py > api.md

