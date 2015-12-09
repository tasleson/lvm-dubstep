
## Interface com.redhat.lvmdbus1.Job ##

#### Methods ####
* Remove 
  * Arguments (None)
  * Returns
      * None

#### Properties ####
* Complete (Boolean (0 is false, 1 is true))
* Percent (uint8_t)
* Result (Oject path)
* get_error (Structure (int32_t, String))

## Interface com.redhat.lvmdbus1.Lv ##

#### Methods ####
* Move 
  * Arguments
      * pv_src_obj (Oject path)
      * pv_source_range (Structure (uint64_t, uint64_t))
      * pv_dest_obj (Oject path)
      * pv_dest_range (Structure (uint64_t, uint64_t))
      * move_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Remove 
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Rename 
  * Arguments
      * name (String)
      * tmo (int32_t)
      * rename_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Snapshot 
  * Arguments
      * name (String)
      * optional_size (uint64_t)
      * tmo (int32_t)
      * snapshot_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* TagsAdd 
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* TagsDel 
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path

#### Properties ####
* DataPercent (uint32_t)
* Devices (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t, String)))
* IsThinPool (Boolean (0 is false, 1 is true))
* IsThinVolume (Boolean (0 is false, 1 is true))
* Name (String)
* OriginLv (Oject path)
* Path (String)
* PoolLv (Oject path)
* SegType (Array of String )
* SizeBytes (uint64_t)
* Tags (Array of String )
* Uuid (String)
* Vg (Oject path)

## Interface com.redhat.lvmdbus1.Manager ##

#### Methods ####
* ExternalEvent 
  * Arguments
      * event (String)
      * lvm_id (String)
      * lvm_uuid (String)
      * seqno (uint32_t)
  * Returns
      * int32_t
* LookUpByLvmId 
  * Arguments
      * key (String)
  * Returns
      * Oject path
* PvCreate 
  * Arguments
      * device (String)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* Refresh 
  * Arguments (None)
  * Returns
      * uint64_t
* VgCreate 
  * Arguments
      * name (String)
      * pv_object_paths (Array of Oject path )
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)

#### Properties ####
* Version (uint64_t)

## Interface com.redhat.lvmdbus1.Pv ##

#### Methods ####
* AllocationEnabled 
  * Arguments
      * yes (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * allocation_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* ReSize 
  * Arguments
      * new_size_bytes (uint64_t)
      * tmo (int32_t)
      * resize_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Remove 
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Oject path

#### Properties ####
* Allocatable (Boolean (0 is false, 1 is true))
* BaSizeBytes (uint64_t)
* BaStart (uint64_t)
* DevSizeBytes (uint64_t)
* Exportable (Boolean (0 is false, 1 is true))
* Fmt (String)
* FreeBytes (uint64_t)
* Lv (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t)))
* MdaFreeBytes (uint64_t)
* MdaSizeBytes (uint64_t)
* Missing (Boolean (0 is false, 1 is true))
* Name (String)
* PeAllocCount (uint64_t)
* PeCount (uint64_t)
* PeSegments (Array of Structure (uint64_t, uint64_t))
* PeStart (uint64_t)
* SizeBytes (uint64_t)
* Tags (Array of String )
* UsedBytes (uint64_t)
* Uuid (String)
* Vg (Oject path)

## Interface com.redhat.lvmdbus1.ThinPool ##

#### Methods ####
* LvCreate 
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* Move 
  * Arguments
      * pv_src_obj (Oject path)
      * pv_source_range (Structure (uint64_t, uint64_t))
      * pv_dest_obj (Oject path)
      * pv_dest_range (Structure (uint64_t, uint64_t))
      * move_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Remove 
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Rename 
  * Arguments
      * name (String)
      * tmo (int32_t)
      * rename_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Snapshot 
  * Arguments
      * name (String)
      * tmo (int32_t)
      * optional_size (uint64_t)
      * snapshot_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)

#### Properties ####
* DataPercent (uint32_t)
* Devices (Array of Structure (Oject path, Array of Structure (uint64_t, uint64_t, String)))
* IsThinPool (Boolean (0 is false, 1 is true))
* IsThinVolume (Boolean (0 is false, 1 is true))
* Name (String)
* OriginLv (Oject path)
* Path (String)
* PoolLv (Oject path)
* SegType (Array of String )
* SizeBytes (uint64_t)
* Tags (Array of String )
* Uuid (String)
* Vg (Oject path)

## Interface com.redhat.lvmdbus1.Vg ##

#### Methods ####
* Change 
  * Arguments
      * tmo (int32_t)
      * change_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Extend 
  * Arguments
      * pv_object_paths (Array of Oject path )
      * tmo (int32_t)
      * extend_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* LvCreateLinear 
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * thin_pool (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* LvCreateMirror 
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * num_copies (uint32_t)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* LvCreateRaid 
  * Arguments
      * name (String)
      * raid_type (String)
      * size_bytes (uint64_t)
      * num_stripes (uint32_t)
      * stripe_size_kb (uint32_t)
      * thin_pool (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* LvCreateStriped 
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * num_stripes (uint32_t)
      * stripe_size_kb (uint32_t)
      * thin_pool (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Oject path, Oject path)
* PvTagsAdd 
  * Arguments
      * pvs (Array of Oject path )
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* PvTagsDel 
  * Arguments
      * pvs (Array of Oject path )
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Reduce 
  * Arguments
      * missing (Boolean (0 is false, 1 is true))
      * pv_object_paths (Array of Oject path )
      * tmo (int32_t)
      * reduce_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Remove 
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* Rename 
  * Arguments
      * name (String)
      * tmo (int32_t)
      * rename_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* TagsAdd 
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path
* TagsDel 
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Oject path

#### Properties ####
* AllocAnywhere (Boolean (0 is false, 1 is true))
* AllocCling (Boolean (0 is false, 1 is true))
* AllocContiguous (Boolean (0 is false, 1 is true))
* AllocNormal (Boolean (0 is false, 1 is true))
* Clustered (Boolean (0 is false, 1 is true))
* Exportable (Boolean (0 is false, 1 is true))
* ExtentCount (uint64_t)
* ExtentSizeBytes (uint64_t)
* Fmt (String)
* FreeBytes (uint64_t)
* FreeCount (uint64_t)
* LvCount (uint64_t)
* Lvs (Array of Oject path )
* MaxLv (uint64_t)
* MaxPv (uint64_t)
* MdaCount (uint64_t)
* MdaFree (uint64_t)
* MdaSizeBytes (uint64_t)
* MdaUsedCount (uint64_t)
* Name (String)
* Partial (Boolean (0 is false, 1 is true))
* Profile (String)
* PvCount (uint64_t)
* Pvs (Array of Oject path )
* Readable (Boolean (0 is false, 1 is true))
* Seqno (uint64_t)
* SizeBytes (uint64_t)
* SnapCount (uint64_t)
* SysId (String)
* Tags (Array of String )
* Uuid (String)
* Writeable (Boolean (0 is false, 1 is true))
