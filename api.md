
## Interface com.redhat.lvm1.thinpool ##

#### Methods ####
* LvCreate 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * size_bytes (uint64_t)
  * Returns
      * Oject path
* Remove 
  * Arguments (None)
  * Returns
      * None

#### Properties ####
* vg (Oject path)
* path (String)
* uuid (String)
* tags (Array of String )
* pool_lv (Oject path)
* size_bytes (String)
* origin_lv (Oject path)
* name (String)
* attr (String)
* devices (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t)))
* data_percent (int32_t)

## Interface com.redhat.lvm1.pv ##

#### Methods ####
* AllocationEnabled 
  * Arguments
      * yes (Boolean (0 is false, 1 is true))
  * Returns
      * None
* ReSize 
  * Arguments
      * new_size_bytes (uint64_t)
  * Returns
      * None
* Remove 
  * Arguments (None)
  * Returns
      * None

#### Properties ####
* allocatable (Boolean (0 is false, 1 is true))
* pe_segments (Array of Structure (uint64_t, uint64_t))
* fmt (String)
* lv (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t)))
* size_bytes (uint64_t)
* pe_start (uint64_t)
* pe_alloc_count (uint64_t)
* ba_size_bytes (uint64_t)
* name (String)
* pe_count (uint64_t)
* used_bytes (uint64_t)
* vg (Oject path)
* free_bytes (uint64_t)
* exportable (Boolean (0 is false, 1 is true))
* missing (Boolean (0 is false, 1 is true))
* tags (Array of String )
* mda_free_bytes (uint64_t)
* mda_size_bytes (uint64_t)
* dev_size_bytes (uint64_t)
* uuid (String)
* ba_start (uint64_t)

## Interface com.redhat.lvm1.vg ##

#### Methods ####
* LvCreateStriped 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * size_bytes (uint64_t)
      * num_stripes (uint32_t)
      * stripe_size_kb (uint32_t)
      * thin_pool (Boolean (0 is false, 1 is true))
  * Returns
      * Oject path
* Extend 
  * Arguments
      * pv_object_paths (Array of Oject path )
  * Returns
      * None
* LvCreateMirror 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * size_bytes (uint64_t)
      * num_copies (uint32_t)
  * Returns
      * Oject path
* Reduce 
  * Arguments
      * missing (Boolean (0 is false, 1 is true))
      * pv_object_paths (Array of Oject path )
  * Returns
      * None
* Remove 
  * Arguments (None)
  * Returns
      * None
* LvCreate 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * size_bytes (uint64_t)
  * Returns
      * Oject path
* LvCreateRaid 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * raid_type (String)
      * size_bytes (uint64_t)
      * num_stripes (uint32_t)
      * stripe_size_kb (uint32_t)
      * thin_pool (Boolean (0 is false, 1 is true))
  * Returns
      * Oject path
* Change 
  * Arguments
      * change_options (Dictionary:{String, Variant})
  * Returns
      * None
* LvCreateLinear 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * name (String)
      * size_bytes (uint64_t)
      * thin_pool (Boolean (0 is false, 1 is true))
  * Returns
      * Oject path

#### Properties ####
* alloc_contiguous (Boolean (0 is false, 1 is true))
* partial (Boolean (0 is false, 1 is true))
* alloc_normal (Boolean (0 is false, 1 is true))
* uuid (String)
* seqno (uint64_t)
* lv_count (uint64_t)
* clustered (Boolean (0 is false, 1 is true))
* size_bytes (uint64_t)
* name (String)
* mda_count (uint64_t)
* mda_used_count (uint64_t)
* free_count (uint64_t)
* snap_count (uint64_t)
* max_pv (uint64_t)
* tags (Array of String )
* mda_size_bytes (uint64_t)
* pv_count (uint64_t)
* pvs (Array of Oject path )
* fmt (String)
* readable (Boolean (0 is false, 1 is true))
* sys_id (String)
* mda_free (uint64_t)
* alloc_anywhere (Boolean (0 is false, 1 is true))
* lvs (Array of Oject path )
* extent_size_bytes (uint64_t)
* writeable (Boolean (0 is false, 1 is true))
* free_bytes (uint64_t)
* extent_count (uint64_t)
* max_lv (uint64_t)
* profile (String)
* exportable (Boolean (0 is false, 1 is true))
* alloc_cling (Boolean (0 is false, 1 is true))

## Interface com.redhat.lvm1.Manager ##

#### Methods ####
* PvCreate 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * device (String)
  * Returns
      * Oject path
* VgCreate 
  * Arguments
      * create_options (Dictionary:{String, Variant})
      * pv_object_paths (Array of Oject path )
      * name (String)
  * Returns
      * Oject path

#### Properties ####

## Interface com.redhat.lvm1.lv ##

#### Methods ####
* Move 
  * Arguments
      * move_options (Dictionary:{String, Variant})
      * pv_src_obj (Oject path)
      * pv_source_range (Structure (uint64_t, uint64_t))
      * pv_dest_obj (Oject path)
      * pv_dest_range (Structure (uint64_t, uint64_t))
  * Returns
      * Oject path
* Snapshot 
  * Arguments
      * snapshot_options (Dictionary:{String, Variant})
      * name (String)
      * optional_size (uint64_t)
  * Returns
      * Oject path
* Remove 
  * Arguments (None)
  * Returns
      * None

#### Properties ####
* vg (Oject path)
* path (String)
* size_bytes (String)
* name (String)
* attr (String)
* tags (Array of String )
* pool_lv (Oject path)
* uuid (String)
* devices (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t)))
* data_percent (int32_t)
* is_thin_volume (Boolean (0 is false, 1 is true))
* origin_lv (Oject path)
