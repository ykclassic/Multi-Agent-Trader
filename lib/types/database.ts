export type AssetClass="crypto"|"forex";
export type Database={public:{Tables:{
  workspaces:{Row:{id:string;owner_id:string;name:string;slug:string;created_at:string;updated_at:string}};
  workspace_members:{Row:{workspace_id:string;user_id:string;role:"owner"|"admin"|"trader"|"viewer";created_at:string}};
  assets:{Row:{id:string;symbol:string;name:string;asset_class:AssetClass;is_active:boolean}};
  venues:{Row:{id:string;code:string;name:string;asset_class:AssetClass;is_active:boolean}};
  instruments:{Row:{id:string;venue_id:string;asset_id:string;symbol:string;base_symbol:string;quote_symbol:string;instrument_type:string;is_active:boolean}};
  strategies:{Row:{id:string;workspace_id:string;name:string;slug:string;asset_class:AssetClass;status:string;created_at:string;updated_at:string}};
  strategy_versions:{Row:{id:string;strategy_id:string;version:number;definition:Record<string,unknown>;created_at:string}};
};Views:{};Functions:{};Enums:{};CompositeTypes:{}}};