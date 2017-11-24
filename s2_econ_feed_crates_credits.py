## Dag for Live Feed to Economy simulation 
## This DAG will generate results for Armory Credits Gain an Spend  Per Day and Also Crates Gain Per Day by Source
## The dags will be executed to cover last three days at any execution to ensure we don't missing anty late updated data 

import airflow
from datetime import timedelta, datetime, time
from airflow.operators.python_operator import PythonOperator
from airflow.operators.sensors import TimeSensor
from quboleWrapper import qubole_wrapper, export_to_rdms

query_type = 'dev_presto'

# Set expected runtime in seconds, setting to 0 is 7200 seconds
expected_runtime = 0

# The group that owns this DAG
owner = "Analytic Services"

default_args = {
    'owner': owner,
    'depends_on_past': False,
    'start_date': datetime(2017, 11, 21),
    'schedule_interval': '@daily'
}

dag = airflow.DAG(dag_id='S2_Econ_Feed_to_Sim_Crates_Credits',
                  default_args=default_args
                  )

# Start running at this time
start_time_task = TimeSensor(target_time=time(6, 30),
                             task_id='start_time_task',
                             dag=dag
                             )

current_date = (datetime.now()).date()
## Get date trailing back to last three days 
stats_date = current_date - timedelta(days=3)

z = '1'

def qubole_operator(task_id, sql, retries, retry_delay, dag):
    return PythonOperator(
        task_id=task_id,
        python_callable=qubole_wrapper,
        provide_context=True,
        retries=retries,
        retry_delay=retry_delay,
        # schedule_interval=None,
        pool='presto_default_pool',
        op_kwargs={'db_type': query_type,
                   'raw_sql': sql,
                   'expected_runtime': expected_runtime,
                   'dag_id': dag.dag_id,
                   'task_id': task_id
                   },
        templates_dict={'ds': '{{ ds }}'},
        dag=dag)


def export_to_rdms_operator(task_id, table_name, retries, retry_delay, dag):
    return PythonOperator(
        task_id=task_id,
        python_callable=export_to_rdms,
        provide_context=True,
        retries=retries,
        retry_delay=retry_delay,
        pool='hive_default_pool',
        op_kwargs={'table_name': table_name,
                   'expected_runtime': expected_runtime,
                   'dag_id': dag.dag_id,
                   'task_id': task_id
                   },
        templates_dict=None,
        dag=dag)

insert_armory_credits_gain_sql = """Insert overwrite table as_s2.s2_armory_credits_gain_source 
with temp_currecny_balances as 

(
select a.* 
from 
(
-- Creating a Union of three source of Currrency Balance changes, currency Balance View can be used but ignnored since it does not have event info reasons 
select distinct context_headers_title_id_s
,context_data_mmp_transaction_id_s
,context_data_client_transaction_id_s 
,context_headers_source_s
,context_headers_env_s
,context_headers_uuid_s
,context_headers__event_type_s
,context_headers_user_id_s
,context_headers_timestamp_s
,currency_id_l
,balance_new_l
,balance_old_l
, 'Pawn Items' as event_info_reason_s 
, dt 
from ads_ww2.fact_mkt_pawnitems_data_userdatachanges_currencybalances 
where dt >= date('%s')
and currency_id_l = 6

union all 

select distinct a.context_headers_title_id_s
,a.context_data_mmp_transaction_id_s 
,a.context_data_client_transaction_id_s 
,a.context_headers_source_s
,a.context_headers_env_s
,a.context_headers_uuid_s
,a.context_headers__event_type_s
,a.context_headers_user_id_s
,a.context_headers_timestamp_s
,a.currency_id_l
,a.balance_new_l
,a.balance_old_l 
,b.event_info_reason_s 
,a.dt
from ads_ww2.fact_mkt_consumeawards_data_userdatachanges_currencybalances a 
join ads_ww2.fact_mkt_consumeawards_data b 
on a.context_headers_user_id_s = b.context_headers_user_id_s 
and a.context_data_mmp_transaction_id_s = b.context_data_mmp_transaction_id_s 
and b.client_transaction_id_s = a.context_data_client_transaction_id_s 
where a.dt >= date('%s')
and currency_id_l = 6

union all 

select distinct a.context_headers_title_id_s
,a.context_data_mmp_transaction_id_s 
,a.context_data_client_transaction_id_s 
,a.context_headers_source_s
,a.context_headers_env_s
,a.context_headers_uuid_s
,a.context_headers__event_type_s
,a.context_headers_user_id_s
,a.context_headers_timestamp_s
,a.currency_id_l
,a.balance_new_l
,a.balance_old_l 
,'Purchase Skus' as event_info_reason_s 
,a.dt
from ads_ww2.fact_mkt_purchaseskus_data_userdatachanges_currencybalances  a 
where dt >= date('%s')
and currency_id_l = 6
) a join 

-- Considering only the isers who had played at least one public match 

(
select distinct dt, context_headers_title_id_s, context_data_players_client_user_id_l from ads_ww2.fact_mp_match_data_players 
where dt >= date('%s')
and context_data_match_common_is_private_match_b = FALSE
) c 
on a.dt = c.dt 
and a.context_headers_title_id_s = c.context_headers_title_id_s 
and a.context_headers_user_id_s = cast(context_data_players_client_user_id_l as varchar)
) 

select currency_id, event_info_reason_s, sum(currency_gained)*pow(b.unique_users,-1) as currency_gained, sum(currency_spent)*pow(b.unique_users,-1) as currency_spent, b.unique_users , a.dt 
from 

-- Adding a Mapping for all the currrency ids

(select dt, context_headers_user_id_s, case when currency_id_l = 1 then 'XP' 
                 when currency_id_l = 2 then 'COD Points'
				 when currency_id_l = 3 then 'Clan Token'
				 when currency_id_l = 4 then 'Prestige Token'
				 when currency_id_l = 5 then 'Supply Key'
				 when currency_id_l = 6 then 'Armory Credit'
				 when currency_id_l = 7 then 'Social XP'
				 when currency_id_l = 8 then 'Double XP'
				 when currency_id_l = 9 then 'Double Division XP'
				 when currency_id_l = 10 then 'Double Weapon XP'
				 when currency_id_l = 11 then 'Double Loot'
				 when currency_id_l = 12 then 'Double XP Daily Time' end as currency_id 
, case when event_info_reason_s like '%%daily_ch%%' then 'Daily Chalange' 
       when event_info_reason_s like '%%social_rank%%' then 'Social Rank Progress' 
	   when event_info_reason_s like '%%payroll_officer%%' then 'Payroll Officer' 
	   
	   -- Confirmed from my data that Supply Drop essentially Daily login as daily logins are result of opening of supply drops by the ID 65,68,69 etc
	   
	   when event_info_reason_s like '%%Supply Drop%%' then 'Daily Login' 
	   when event_info_reason_s like '%%watch_sd%%' then 'Watch Supply Drop' 
	   else event_info_reason_s end as event_info_reason_s
			 
	, sum(currency_gained) as currency_gained, sum(currency_spent) as currency_spent 
from 
(select dt, context_headers_user_id_s, currency_id_l, event_info_reason_s, balance_new_l , balance_old_l, context_headers__event_type_s
, context_headers_timestamp_s 
, to_unixtime(from_iso8601_timestamp(context_headers_timestamp_s))
, (case when balance_new_l > balance_old_l then (balance_new_l - balance_old_l )  else 0 end) as currency_gained 
, (case when balance_new_l < balance_old_l then (balance_old_l - balance_new_l )  else 0 end) as currency_spent 
from temp_currecny_balances
) 

group by 1,2,3,4
) a join 
( 
select dt, sum(unique_users) as unique_users 
from 
( select dt, context_headers_title_id_s, count(distinct context_data_players_client_user_id_l) as unique_users 
from ads_ww2.fact_mp_match_data_players 
where dt >= date('%s')
and context_data_match_common_is_private_match_b = FALSE 
group by 1,2 )
group by 1 
) b 
on a.dt = b.dt 
group by 1,2,5,6
order by 1,2,3 """ % (stats_date, stats_date, stats_date, stats_date, stats_date) 

## Create a task for Armory credits Gain SQL

insert_armory_credits_gain_task = qubole_operator('insert_armory_credits_gain',
                                              insert_armory_credits_gain_sql, 2, timedelta(seconds=600), dag)

## SQL for Crates Gain Per Day 

insert_crates_gain_sql = '''Insert overwrite table as_s2.s2_common_rare_crates_gain_source  
with temp_inventory_items as 
(

-- Append all the source datas from Market Data Inventory Items 
-- Item Id 1 and 2 are present in only the below mentioned two tables 

select a.* 
from 
(
select dt, context_headers_title_id_s, context_headers_user_id_s, item_id_l
, case when quantity_old_l is null then 0 else quantity_old_l end as quantity_old_l
, case when quantity_new_l is null then 0 else quantity_new_l end as quantity_new_l
, 'Award Product' as event_info_reason_s 
from ads_ww2.fact_mkt_awardproduct_data_userdatachanges_inventoryitems 
where dt >= date('%s')
and item_id_l in (1,2,5,6) 

union all 

select a.dt, a.context_headers_title_id_s, a.context_headers_user_id_s, a.item_id_l
, case when  a.quantity_old_l is null then 0 else a.quantity_old_l end as quantity_old_l
, case when  a.quantity_new_l is null then 0 else a.quantity_new_l end as quantity_new_l
, coalesce(b.event_info_reason_s , 'Missing Reasons') as event_info_reason_s
from ads_ww2.fact_mkt_consumeawards_data_userdatachanges_inventoryitems a 
left join ads_ww2.fact_mkt_consumeawards_data b 

on a.context_headers_user_id_s = b.context_headers_user_id_s 
and a.context_data_mmp_transaction_id_s = b.context_data_mmp_transaction_id_s 
and b.client_transaction_id_s = a.context_data_client_transaction_id_s 
where a.dt >= date('%s')
and a.item_id_l in (1,2,5,6) 

union all 

select dt, context_headers_title_id_s, context_headers_user_id_s, item_id_l 
, case when quantity_old_l is null then 0 else quantity_old_l end as quantity_old_l
, case when quantity_new_l is null then 0 else quantity_new_l end as quantity_new_l
, 'Purchase Skus' as event_info_reason_s 
from ads_ww2.fact_mkt_purchaseskus_data_userdatachanges_inventoryitems 
where dt >= date('%s')
and item_id_l in (1,2,5,6) 
) a 

join 

-- Consider only the users who have played at least one public match 

 (select distinct dt, context_headers_title_id_s, context_data_players_client_user_id_l 
 from ads_ww2.fact_mp_match_data_players where dt >= date('%s')
and context_data_match_common_is_private_match_b = FALSE) c 
on a.dt = c.dt 
and a.context_headers_title_id_s = c.context_headers_title_id_s
and a.context_headers_user_id_s = cast(c.context_data_players_client_user_id_l as varchar)
) 

-- Marking the Crate Types
-- Grouping Event Reasons based on the character sequences present in the event reason info 

select case when item_id_l = 1 then 'MP Common Crate' 
                when item_id_l = 2 then 'MP Rare Crate' 
				when item_id_l = 5 then 'ZM Common Crate' 
				when item_id_l = 6 then 'ZM Rare Crate' end as crate_type
	, case when event_info_reason_s like '%%daily_ch%%' then 'Daily Challenge' 
	       when event_info_reason_s like '%%weekly_ch%%' then 'Weekly Chalenge' 
		   when event_info_reason_s like '%%contract%%' then 'Contracts' 
		   when event_info_reason_s like '%%social_rank%%' then 'Social Rank Progress' 
		   when event_info_reason_s like '%%gear_bitfield_zm%%' then 'Zombies Gear' 
		   when event_info_reason_s like '%%player_level%%' then 'MP Player Level Progress' 
		   when event_info_reason_s like '%%special_ch%%' then 'Special Challenges' 
		   when event_info_reason_s like '%%watch_sd%%' then 'Watch Supply Drop' 
		   when event_info_reason_s like '%%hq_tutorial%%' then 'HQ Tutorial Complete' 
		   when event_info_reason_s like '%%killed_boss%%' then 'ZM Boss Kill'
		   when event_info_reason_s like '%%player_zm_level%%' then 'ZM Player Level Progress' 
		   else event_info_reason_s end as event_group 
	, event_info_reason_s 
	-- Only Consider the events which are of gain type 
	, sum(case when quantity_new_l > quantity_old_l then quantity_new_l - quantity_old_l else 0 end) as sum_crates_gain 
	-- Get Count of Users who actually had change for the particular crate type and event reason 
	, count(distinct context_headers_user_id_s) as users_with_crate_change 
	-- Map Unique users of the day from Source temporary table 
	, b.unique_users as total_dau, a.dt
from temp_inventory_items a 
	join 
( 
select dt, sum(unique_users) as unique_users 
from 
(select dt, context_headers_title_id_s, count(distinct context_data_players_client_user_id_l) as unique_users 
from ads_ww2.fact_mp_match_data_players 
where dt >= date('%s')
and context_data_match_common_is_private_match_b = FALSE 
group by 1,2)
group by 1 
) b 
on a.dt = b.dt 
where a.quantity_new_l > a.quantity_old_l
group by 1,2,3, 6,7''' %(stats_date, stats_date, stats_date, stats_date, stats_date) 

insert_crates_gain_task = qubole_operator('insert_crates_gain',
                                              insert_crates_gain_sql, 2, timedelta(seconds=600), dag)

											  
# Wire up the DAG
insert_armory_credits_gain_task.set_upstream(start_time_task)
insert_crates_gain_task.set_upstream(start_time_task)
