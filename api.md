
## Interface com.redhat.lvmdbus1.CachePool ##

#### Methods ####
* CacheLv
  * Arguments
      * lv_object (Object path)
      * tmo (int32_t)
      * cache_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)

#### Properties ####
* DataLv (Object path)
* MetaDataLv (Object path)

## Interface com.redhat.lvmdbus1.CachedLv ##

#### Methods ####
* DetachCachePool
  * Arguments
      * destroy_cache (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * detach_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)

#### Properties ####
* CachePool (Object path)

## Interface com.redhat.lvmdbus1.Job ##

#### Methods ####
* Remove
  * Arguments (None)
  * Returns
      * None
* Wait
  * Arguments
      * timeout (int32_t)
  * Returns
      * Boolean (0 is false, 1 is true)

#### Properties ####
* Complete (Boolean (0 is false, 1 is true))
* GetError (Structure (int32_t, String))
* Percent (double)
* Result (Object path)

## Interface com.redhat.lvmdbus1.Lv ##

#### Methods ####
* Activate
  * Arguments
      * control_flags (uint64_t)
      * tmo (int32_t)
      * activate_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Deactivate
  * Arguments
      * control_flags (uint64_t)
      * tmo (int32_t)
      * activate_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Move
  * Arguments
      * pv_src_obj (Object path)
      * pv_source_range (Structure (uint64_t, uint64_t))
      * pv_dests_and_ranges (Array of Structure (Object path, uint64_t, uint64_t))
      * tmo (int32_t)
      * move_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Remove
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Rename
  * Arguments
      * name (String)
      * tmo (int32_t)
      * rename_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Resize
  * Arguments
      * new_size_bytes (uint64_t)
      * pv_dests_and_ranges (Array of Structure (Object path, uint64_t, uint64_t))
      * tmo (int32_t)
      * resize_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Snapshot
  * Arguments
      * name (String)
      * optional_size (uint64_t)
      * tmo (int32_t)
      * snapshot_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* TagsAdd
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* TagsDel
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path

#### Properties (None) ####

## Interface com.redhat.lvmdbus1.LvCommon ##

#### Methods ####

#### Properties ####
* Active (Boolean (0 is false, 1 is true))
* AllocationPolicy (Structure (String, String))
* Attr (String)
* CopyPercent (uint32_t)
* DataPercent (uint32_t)
* Devices (Array of Structure (Object path, Array of Structure (uint64_t, uint64_t, String)))
* FixedMinor (Boolean (0 is false, 1 is true))
* Health (Structure (String, String))
* HiddenLvs (Array of Object path )
* IsThinPool (Boolean (0 is false, 1 is true))
* IsThinVolume (Boolean (0 is false, 1 is true))
* MetaDataPercent (uint32_t)
* MetaDataSizeBytes (uint64_t)
* MovePv (Object path)
* Name (String)
* OriginLv (Object path)
* Path (String)
* Permissions (Structure (String, String))
* PoolLv (Object path)
* Roles (Array of String )
* SegType (Array of String )
* SizeBytes (uint64_t)
* SkipActivation (Boolean (0 is false, 1 is true))
* SnapPercent (uint32_t)
* State (Structure (String, String))
* SyncPercent (uint32_t)
* Tags (Array of String )
* TargetType (Structure (String, String))
* Uuid (String)
* Vg (Object path)
* VolumeType (Structure (String, String))
* ZeroBlocks (Boolean (0 is false, 1 is true))

## Interface com.redhat.lvmdbus1.Manager ##

#### Methods ####
* ExternalEvent
  * Arguments
      * command (String)
  * Returns
      * int32_t
* LookUpByLvmId
  * Arguments
      * key (String)
  * Returns
      * Object path
* PvCreate
  * Arguments
      * device (String)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* PvScan
  * Arguments
      * activate (Boolean (0 is false, 1 is true))
      * cache (Boolean (0 is false, 1 is true))
      * device_paths (Array of String )
      * major_minors (Array of Structure (int32_t, int32_t))
      * tmo (int32_t)
      * scan_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Refresh
  * Arguments (None)
  * Returns
      * uint64_t
* UseLvmShell
  * Arguments
      * yes_no (Boolean (0 is false, 1 is true))
  * Returns
      * Boolean (0 is false, 1 is true)
* VgCreate
  * Arguments
      * name (String)
      * pv_object_paths (Array of Object path )
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)

#### Properties ####
* Version (String)

## Interface com.redhat.lvmdbus1.Pv ##

#### Methods ####
* AllocationEnabled
  * Arguments
      * yes (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * allocation_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* ReSize
  * Arguments
      * new_size_bytes (uint64_t)
      * tmo (int32_t)
      * resize_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Remove
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Object path

#### Properties ####
* Allocatable (Boolean (0 is false, 1 is true))
* BaSizeBytes (uint64_t)
* BaStart (uint64_t)
* DevSizeBytes (uint64_t)
* Exportable (Boolean (0 is false, 1 is true))
* Fmt (String)
* FreeBytes (uint64_t)
* Lv (Array of Structure (Object path, Array of Structure (uint64_t, uint64_t, String)))
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
* Vg (Object path)

## Interface com.redhat.lvmdbus1.Snapshot ##

#### Methods ####
* Merge
  * Arguments
      * tmo (int32_t)
      * merge_options (Dictionary:{String, Variant})
  * Returns
      * Object path

#### Properties (None) ####

## Interface com.redhat.lvmdbus1.ThinPool ##

#### Methods ####
* LvCreate
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)

#### Properties ####
* DataLv (Object path)
* MetaDataLv (Object path)

## Interface com.redhat.lvmdbus1.Vg ##

#### Methods ####
* Activate
  * Arguments
      * control_flags (uint64_t)
      * tmo (int32_t)
      * activate_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* AllocationPolicySet
  * Arguments
      * policy (String)
      * tmo (int32_t)
      * policy_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Change
  * Arguments
      * tmo (int32_t)
      * change_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* CreateCachePool
  * Arguments
      * meta_data_lv (Object path)
      * data_lv (Object path)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* CreateThinPool
  * Arguments
      * meta_data_lv (Object path)
      * data_lv (Object path)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* Deactivate
  * Arguments
      * control_flags (uint64_t)
      * tmo (int32_t)
      * activate_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Extend
  * Arguments
      * pv_object_paths (Array of Object path )
      * tmo (int32_t)
      * extend_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* LvCreate
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * pv_dests_and_ranges (Array of Structure (Object path, uint64_t, uint64_t))
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* LvCreateLinear
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * thin_pool (Boolean (0 is false, 1 is true))
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* LvCreateMirror
  * Arguments
      * name (String)
      * size_bytes (uint64_t)
      * num_copies (uint32_t)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
* LvCreateRaid
  * Arguments
      * name (String)
      * raid_type (String)
      * size_bytes (uint64_t)
      * num_stripes (uint32_t)
      * stripe_size_kb (uint32_t)
      * tmo (int32_t)
      * create_options (Dictionary:{String, Variant})
  * Returns
      * Structure (Object path, Object path)
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
      * Structure (Object path, Object path)
* MaxLvSet
  * Arguments
      * number (uint64_t)
      * tmo (int32_t)
      * max_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* MaxPvSet
  * Arguments
      * number (uint64_t)
      * tmo (int32_t)
      * max_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Move
  * Arguments
      * pv_src_obj (Object path)
      * pv_source_range (Structure (uint64_t, uint64_t))
      * pv_dests_and_ranges (Array of Structure (Object path, uint64_t, uint64_t))
      * tmo (int32_t)
      * move_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* PvTagsAdd
  * Arguments
      * pvs (Array of Object path )
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* PvTagsDel
  * Arguments
      * pvs (Array of Object path )
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Reduce
  * Arguments
      * missing (Boolean (0 is false, 1 is true))
      * pv_object_paths (Array of Object path )
      * tmo (int32_t)
      * reduce_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Remove
  * Arguments
      * tmo (int32_t)
      * remove_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* Rename
  * Arguments
      * name (String)
      * tmo (int32_t)
      * rename_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* TagsAdd
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* TagsDel
  * Arguments
      * tags (Array of String )
      * tmo (int32_t)
      * tag_options (Dictionary:{String, Variant})
  * Returns
      * Object path
* UuidGenerate
  * Arguments
      * tmo (int32_t)
      * options (Dictionary:{String, Variant})
  * Returns
      * Object path

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
* Lvs (Array of Object path )
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
* Pvs (Array of Object path )
* Readable (Boolean (0 is false, 1 is true))
* Resizeable (Boolean (0 is false, 1 is true))
* Seqno (uint64_t)
* SizeBytes (uint64_t)
* SnapCount (uint64_t)
* SysId (String)
* Tags (Array of String )
* Uuid (String)
* Writeable (Boolean (0 is false, 1 is true))
