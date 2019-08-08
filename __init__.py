#Copyright (c) 2012 PointAtStuff
#This code is open source under the zlib license.

bl_info = {
    "name": "Real Time Animation",
    "author": "PointAtStuff Update to 2.80 by Sav Martin",
    "version": (2, 6, 0),
    "blender": (2, 80, 0),
    "location": "Menu on left side of 3D View >> Animation category",
    "category": "Animation",
    "description": "Animate in real time by recording object motion",
    "warning": "",
    "wiki_url": "",
    "tracker_url": ""}

import bpy
from mathutils import *
from math import *
from bpy_extras.view3d_utils import *

###########
#Gui panel
###########
class VIEW3D_PT_rtmanim_panel(bpy.types.Panel):
    bl_label = "Real Time Animation"
    bl_idname = "VIEW3D_PT_rtmanim_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"
    @classmethod
    def poll(cls, context):
        return (context.mode in ['OBJECT', 'POSE'])

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(context.scene, "rtmanim_time_property")
        row = col.row(align=True)
        row.operator("transform.rtmanim_move", text="L", icon=TRANSFORM_OT_rtmanim_move.pic_shown)
        row.operator("transform.rtmanim_rotate", text="R", icon=TRANSFORM_OT_rtmanim_rotate.pic_shown)
        row.operator("transform.rtmanim_scale", text="S", icon=TRANSFORM_OT_rtmanim_scale.pic_shown)
        row = col.row(align=True)
        row.prop(context.scene, "rtmanim_lkeyframe_frequency_property")
        row.prop(context.scene, "rtmanim_rkeyframe_frequency_property")
        row.prop(context.scene, "rtmanim_skeyframe_frequency_property")
        row = col.row(align=True)
        row.operator("transform.rtmanim_keyframe_insert_prev_location", text = "Prev")
        row.operator("transform.rtmanim_keyframe_insert_next_location", text = "Next")
        row.operator("transform.rtmanim_keyframe_insert_prev_rotation", text = "Prev")
        row.operator("transform.rtmanim_keyframe_insert_next_rotation", text = "Next")
        row.operator("transform.rtmanim_keyframe_insert_prev_scale", text = "Prev")
        row.operator("transform.rtmanim_keyframe_insert_next_scale", text = "Next")    
        row = col.row(align=True)
        row.operator("transform.rtmanim_keyframe_sel_location", text="Sel", icon=TRANSFORM_OT_rtmanim_keyframe_sel_location.pic_shown)
        row.operator("transform.rtmanim_keyframe_sel_rotation", text="Sel", icon=TRANSFORM_OT_rtmanim_keyframe_sel_rotation.pic_shown)
        row.operator("transform.rtmanim_keyframe_sel_scale", text="Sel", icon=TRANSFORM_OT_rtmanim_keyframe_sel_scale.pic_shown)
        row = col.row(align=True)
        row.operator("transform.rtmanim_keyframe_dsel_location", text="Dsel", icon=TRANSFORM_OT_rtmanim_keyframe_dsel_location.pic_shown)
        row.operator("transform.rtmanim_keyframe_dsel_rotation", text="Dsel", icon=TRANSFORM_OT_rtmanim_keyframe_dsel_rotation.pic_shown)
        row.operator("transform.rtmanim_keyframe_dsel_scale", text="Dsel", icon=TRANSFORM_OT_rtmanim_keyframe_dsel_scale.pic_shown)
        row = col.row(align=True)
        row.operator("transform.rtmanim_keyframe_del_location", text="Del", icon=TRANSFORM_OT_rtmanim_keyframe_del_location.pic_shown)
        row.operator("transform.rtmanim_keyframe_del_rotation", text="Del", icon=TRANSFORM_OT_rtmanim_keyframe_del_rotation.pic_shown)
        row.operator("transform.rtmanim_keyframe_del_scale", text="Del", icon=TRANSFORM_OT_rtmanim_keyframe_del_scale.pic_shown)
        col.operator("transform.rtmanim_stop_all", text="Stop All", icon='QUIT')

        col = self.layout.column(align=True)
        col.prop(context.scene, "rtmanim_keyframe_info_property")
        col.operator("transform.rtmanim_info", text="Keyframe Info", icon=TRANSFORM_OT_rtmanim_info.pic_shown)
 
        col = self.layout.column(align=True)
        col.prop(context.scene, "rtmanim_smooth_follow_factor_property")
        row = col.row(align=True)
        row.prop(context.scene, "rtmanim_smooth_follow_x_property")
        row.prop(context.scene, "rtmanim_smooth_follow_y_property")
        row.prop(context.scene, "rtmanim_smooth_follow_z_property")
        col.operator("transform.rtmanim_smooth_follow", text="Smooth Follow", icon=TRANSFORM_OT_rtmanim_smooth_follow.pic_shown)
     
################################################################
#Modal keyframing and time advance operator. Used for recording
#location, rotation, scale. Uses a "singleton modal loop".
################################################################
class TRANSFORM_OT_rtmanim_modal_kf_and_tm(bpy.types.Operator):
    bl_label = "real time animation operator"
    bl_idname = "transform.rtmanim_modal_kf_and_tm"
    bl_description = "real time animation operator"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return True

    #operator control
    op_running=None
    @classmethod
    def stop(cls):
        cls.op_running=False
        cls.anim_data_paths.clear()
        #deactivate buttons
        TRANSFORM_OT_rtmanim_move.deactivate()
        TRANSFORM_OT_rtmanim_rotate.deactivate()
        TRANSFORM_OT_rtmanim_scale.deactivate()
        
    #keyframe insertion
    anim_data_paths=set()
    keyframe_group=None
    objmode_anim_data_paths_to_keyframe_groups = {'location':'Location', 'scale':'Scale',
        'rotation_quaternion':'Rotation', 'rotation_euler':'Rotation', 'rotation_axis_angle':'Rotation'}
    insert_stationary_keyframes=True
    start_frame=None

    #frame advancement
    loops_remaining=None #how many modal loops to skip before advancing time slider
    remembered_time_property=None
    init_modal_update=True

    #various controls
    objects=None
    remembered_frame=None
    remembered_rotation_mode=None
    prev_coords0=dict() #prev coords for object at objects[0]
    @classmethod
    def add_anim_data_path(cls, anim_data_path):
        cls.anim_data_paths.add(anim_data_path)
    @classmethod
    def remove_anim_data_path(cls, anim_data_path):
        cls.anim_data_paths.remove(anim_data_path)
        if len(cls.anim_data_paths) < 1: cls.stop()
    @classmethod #method to get object's rotation anim data path based on object's rotation mode
    def get_rotation_anim_data_path(cls, rotation_mode):
        if rotation_mode[0]=='Q': return 'rotation_quaternion'
        elif rotation_mode[0]=='A': return 'rotation_axis_angle'
        else: return 'rotation_euler'

    def invoke(self, context, event):
        cls = self.__class__

        #various inits
        cls.objects = context.selected_pose_bones if context.mode=='POSE' else context.selected_objects
        cls.anim_data_paths = cls.anim_data_paths & {'location', 'r', 'scale'} #make sure no wrong items in anim_data_paths set
        cls.keyframe_group = "obj.name" if context.mode=='POSE' else "cls.objmode_anim_data_paths_to_keyframe_groups[anim_data_path]"
        cls.start_frame = context.scene.frame_current
        cls.remembered_frame = context.scene.frame_current
        try: cls.objects[0] #check if anything is selected
        except: cls.stop(); return {'CANCELLED'}
        cls.remembered_rotation_mode = cls.objects[0].rotation_mode

        #setup initial keyframe insertion, frame advancement
        cls.insert_stationary_keyframes=True
        cls.loops_remaining = context.scene.rtmanim_time_property
        cls.remembered_time_property = context.scene.rtmanim_time_property
        cls.init_modal_update=True
        
        #initialize prev coords for object at cls.objects[0]
        for anim_data_path in cls.anim_data_paths:
            if anim_data_path=='r': anim_data_path = cls.get_rotation_anim_data_path(cls.objects[0].rotation_mode)
            try: cls.prev_coords0[anim_data_path] = eval('cls.objects[0].'+anim_data_path+'.copy()')
            except: #axis-angle rotation mode doesn't support copy(), so replace with quaternion value instead
                cls.prev_coords0['rotation_axis_angle'] = Quaternion(cls.objects[0].rotation_axis_angle)

        #start modal loop, all this stuff must be at the end of invoke so above code can always run
        if cls.op_running: return {'FINISHED'}
        cls.op_running=True
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(.01, window=context.window)
        self._prev_time_duration = self._timer.time_duration
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        cls = self.__class__

        #######################
        #check if need to stop
        #######################
        cur_objects = context.selected_pose_bones if context.mode=='POSE' else context.selected_objects
        if (cls.op_running!=True or cls.objects!=cur_objects or cls.remembered_frame!=context.scene.frame_current
            or cls.remembered_rotation_mode!=cls.objects[0].rotation_mode):
            cls.stop()
            try: context.window_manager.event_timer_remove(self._timer)
            except: pass
            return {'FINISHED'}

        if event.type=='TIMER' and self._prev_time_duration!=self._timer.time_duration:
            self._prev_time_duration=self._timer.time_duration

            #####################################################################
            #check if object at cls.objects[0] has moved and thus need to update
            #####################################################################
            pass_through=True #if code below doesn't set this to False, it means objects didn't move
            for anim_data_path in cls.anim_data_paths:
                if anim_data_path=='r':
                    #rotation-axis-angle is a special case, since can't copy it need to replace it with quaternion
                    if cls.objects[0].rotation_mode[0]=='A':
                        if cls.prev_coords0['rotation_axis_angle']!=Quaternion(cls.objects[0].rotation_axis_angle):
                            pass_through=False; break
                        continue
                    else: anim_data_path = cls.get_rotation_anim_data_path(cls.objects[0].rotation_mode)
                if cls.prev_coords0[anim_data_path]!=eval('cls.objects[0].'+anim_data_path): pass_through=False; break

            ####################
            #object didn't move
            ####################
            if pass_through:
                #check if time factor changed, updat if so (do only once to not waste cpu work)
                if cls.remembered_time_property!=context.scene.rtmanim_time_property:
                    cls.loops_remaining = context.scene.rtmanim_time_property
                    cls.remembered_time_property = context.scene.rtmanim_time_property
                #insert keyframes when time slider isn't moving (do only once to not waste cpu work)
                if cls.insert_stationary_keyframes:
                    for obj in cls.objects:
                        for anim_data_path in cls.anim_data_paths:
                            if anim_data_path=='r': anim_data_path = cls.get_rotation_anim_data_path(obj.rotation_mode)
                            obj.keyframe_insert(data_path=anim_data_path, group=eval(cls.keyframe_group))
                    context.scene.frame_set(context.scene.frame_current+1)
                    context.scene.frame_set(context.scene.frame_current-1)
                    cls.insert_stationary_keyframes=False
                return {'PASS_THROUGH'}

            ############################
            #here if objects have moved
            ############################
            cls.insert_stationary_keyframes=True #reset insert_stationary_keyframes

            ############################################################################################################
            #For "motion layering", need to insert keyframes on every timer. Because let's say you are recording
            #rotation for a moving object, the object will rotate in place and only update location when a new keyframe 
            #is inserted. So, need to insert keyframes frequently (on every timer) so that the object updates often.
            ############################################################################################################
            #Below applies only during the first instant that object moves. Advance time slider to avoid overwriting the
            #initial keyframe. Need to do this because later code (that inserts keyframes every time) is going to overwrite
            #the initial keyframe, but the object has moved by now and so the initial keyframe would be lost. Note, set
            #timer to low value like .01 sec to prevent this code from causing a slight "blink" during initial time slider advance.
            if cls.init_modal_update:
                context.scene.frame_set(context.scene.frame_current+1)
                cls.remembered_frame = context.scene.frame_current
                cls.init_modal_update = False
            #insert keyframes on every timer
            for obj in cls.objects:
                for anim_data_path in cls.anim_data_paths:
                    if anim_data_path=='r': anim_data_path = cls.get_rotation_anim_data_path(obj.rotation_mode)
                    obj.keyframe_insert(data_path=anim_data_path, group=eval(cls.keyframe_group))
            #Need to move time slider back and forth (to update the scene) after
            #inserting keyframes every time or object jumps to initial position.
            context.scene.frame_set(context.scene.frame_current+1)
            context.scene.frame_set(context.scene.frame_current-1)

            #################################################################
            #Update time slider after user-defined pause. Needs to go after
            #above code or object momentarily freezes on time slider move.
            #################################################################
            if cls.loops_remaining < 1: 
                context.scene.frame_set(context.scene.frame_current+1)
                cls.remembered_frame = context.scene.frame_current
                cls.loops_remaining = context.scene.rtmanim_time_property
                #delete previous location keyframes that are not needed
                if ('location' in cls.anim_data_paths) and ((context.scene.frame_current-cls.start_frame-1)%context.scene.rtmanim_lkeyframe_frequency_property!=0):
                    for obj in cls.objects: obj.keyframe_delete(data_path='location', frame=context.scene.frame_current-1)
                #delete previous rotation keyframes that are not needed
                if ('r' in cls.anim_data_paths) and ((context.scene.frame_current-cls.start_frame-1)%context.scene.rtmanim_rkeyframe_frequency_property!=0):
                    for obj in cls.objects: obj.keyframe_delete(data_path=cls.get_rotation_anim_data_path(obj.rotation_mode), frame=context.scene.frame_current-1)
                #delete previous scale keyframes that are not needed
                if ('scale' in cls.anim_data_paths) and ((context.scene.frame_current-cls.start_frame-1)%context.scene.rtmanim_skeyframe_frequency_property!=0):
                    for obj in cls.objects: obj.keyframe_delete(data_path='scale', frame=context.scene.frame_current-1)
                #done deleting keyframes
            else: cls.loops_remaining-=1

            #######################################################################################################################
            #Update prev coords for object at cls.objects[0]. Note, below code can be factored out into a function (a copy of it 
            #is also used in "invoke"), but can also keep it like this, as "inlined" code (faster since avoids the function call).
            #######################################################################################################################
            for anim_data_path in cls.anim_data_paths:
                if anim_data_path=='r': anim_data_path = cls.get_rotation_anim_data_path(cls.objects[0].rotation_mode)
                try: cls.prev_coords0[anim_data_path] = eval('cls.objects[0].'+anim_data_path+'.copy()')
                except: #axis-angle rotation mode doesn't support copy(), so replace with quaternion value instead
                    cls.prev_coords0['rotation_axis_angle'] = Quaternion(cls.objects[0].rotation_axis_angle)
        
        #keep modal loop going
        return {'PASS_THROUGH'}

#############################
#Location recording operator
#############################
class TRANSFORM_OT_rtmanim_move(bpy.types.Operator):
    bl_label = "Record object location"
    bl_idname = "transform.rtmanim_move"
    bl_description = "Record object location"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.stop() #stop keyframe selecting/deselecting
            TRANSFORM_OT_rtmanim_modal_info_logic.stop() #stop info
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.add_anim_data_path('location')
            rval = bpy.ops.transform.rtmanim_modal_kf_and_tm('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
        else:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.remove_anim_data_path('location')
            cls.deactivate()
        return {'FINISHED'}

#############################
#Rotation recording operator
#############################
class TRANSFORM_OT_rtmanim_rotate(bpy.types.Operator):
    bl_label = "Record object rotation"
    bl_idname = "transform.rtmanim_rotate"
    bl_description = "Record object rotation"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.stop()
            TRANSFORM_OT_rtmanim_modal_info_logic.stop() #stop info
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.add_anim_data_path('r')
            rval = bpy.ops.transform.rtmanim_modal_kf_and_tm('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
        else:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.remove_anim_data_path('r')
            cls.deactivate()
        return {'FINISHED'}

##########################
#Scale recording operator
##########################
class TRANSFORM_OT_rtmanim_scale(bpy.types.Operator):
    bl_label = "Record object scale"
    bl_idname = "transform.rtmanim_scale"
    bl_description = "Record object scale"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.stop()
            TRANSFORM_OT_rtmanim_modal_info_logic.stop() #stop info
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.add_anim_data_path('scale')
            rval = bpy.ops.transform.rtmanim_modal_kf_and_tm('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
        else:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.remove_anim_data_path('scale')
            cls.deactivate()
        return {'FINISHED'}

####################################################################################################
#Function for keyframe searching, uses binary search. Returns list of indexes of 3 keyframe points. 
#They are the keyframe point before current frame, at the current frame, after current frame. If 
#there is no such keyframe point, its value in the list is None.
####################################################################################################
def keyframe_search(keyframe_points, frame):
    #init index values for prev keyframe, overlapping keyframe, next keyframe
    returned_list = [None, None, None]
    #binary search
    imin = 0
    imax = len(keyframe_points)-1
    imid = None
    while(imax >= imin):
        imid = floor((imin+imax)/2)
        if keyframe_points[imid].co.x < frame: imin = imid+1
        elif keyframe_points[imid].co.x > frame: imax = imid-1
        else: #overlapping keyframe
            returned_list[0] = (imid-1) if (imid-1)>=0 else None
            returned_list[1] = imid
            returned_list[2] = imid+1 if (imid+1)<len(keyframe_points) else None
            return returned_list
    #no overlapping keyframe
    if keyframe_points[imid].co.x < frame:
        (returned_list[0], returned_list[1]) = (imid, None)
        returned_list[2] = imid+1 if (imid+1)<len(keyframe_points) else None
    else:
        returned_list[0] = imid-1 if (imid-1)>=0 else None
        (returned_list[1], returned_list[2]) = (None, imid)
    return returned_list

################################################################################
#Function for getting object fcurves. In pose mode, if anim_data_paths_actions 
#is None, returns all the fcurves for currently selected bones. The returned
#fcurves dictionary contains empty lists if nothing is found.
################################################################################
def get_fcurves(context, objects, anim_data_paths_actions, actions_list):
    fcurves = dict() #used for grouping fcurves by action
    for action in actions_list: fcurves[action] = list()

    #####################################################
    #pose mode, get fcurves only for selected pose bones
    #####################################################
    if context.mode=='POSE' and len(context.selected_pose_bones)>0:
        armature = context.selected_pose_bones[0].id_data
        if armature not in objects: #armature should be in objects
            return fcurves
        for fc in armature.animation_data.action.fcurves:
            for b in context.selected_pose_bones:
                if '\"'+b.name+'\"' in fc.data_path:
                    data_path = fc.data_path.split('.')[-1]
                    if anim_data_paths_actions==None: action=actions_list[0]
                    else: action = anim_data_paths_actions.get(data_path)
                    if action in actions_list: 
                        fcurves[action].append(fc) 
                        break #got this fcurve, go to next one

    #####################################################
    #not pose mode, get fcurves for all selected objects
    #####################################################
    else:
        for obj in objects:
            try: obj_fcurves = obj.animation_data.action.fcurves; obj_fcurves[0]
            except: continue #no animation data for object
            for fcurve in obj_fcurves:
                #note, below line also causes bone fcurves to be skipped, so don't need extra check for that
                action = anim_data_paths_actions.get(fcurve.data_path)
                if action in actions_list: fcurves[action].append(fcurve)

    #return the fcurves grouped by their actions
    return fcurves

##################################################
#Function with duplicate keyframe insertion logic
##################################################
def keyframe_insert(context, anim_data_path, prev_or_next):

    curframe = context.scene.frame_current
    #Get list of fcurves. Note, just making up an action called 'i'
    #in order to call the generalized get_fcurves function, this action
    #is not actually used anywhere.
    if anim_data_path=='r': arg={'rotation_quaternion':'i', 'rotation_euler':'i', 'rotation_axis_angle':'i'}
    else: arg={anim_data_path:'i'}
    fcurves = get_fcurves(context, context.selected_objects, arg, ['i'])['i']
    for fcurve in fcurves:

        ####################################
        #insert keyframe for current object
        ####################################
        keyframes = fcurve.keyframe_points
        if prev_or_next == "prev":
            #do quick check for boundaries, otherwise search for the index
            if keyframes[0].co.x >= curframe: pass
            elif keyframes[-1].co.x < curframe: fcurve.keyframe_points.insert(curframe, keyframes[-1].co.y)
            else:
                index = keyframe_search(keyframes, curframe)[0]
                keyframes.insert(curframe, keyframes[index].co.y)
        else: #next
            #do quick check for boundaries, otherwise search for the index
            if keyframes[-1].co.x <= curframe: pass
            elif keyframes[0].co.x > curframe: fcurve.keyframe_points.insert(curframe, keyframes[0].co.y)
            else:
                index = keyframe_search(keyframes, curframe)[2]
                keyframes.insert(curframe, keyframes[index].co.y)

    #update
    context.scene.frame_set(context.scene.frame_current+1) 
    context.scene.frame_set(context.scene.frame_current-1)

#################################################
#Previous location keyframe duplication operator
#################################################
class TRANSFORM_OT_rtmanim_keyframe_insert_prev_location(bpy.types.Operator):
    bl_label = "Duplicate previous location keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_prev_location"
    bl_description = "Duplicate previous location keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'location', 'prev')
        return {'FINISHED'}

#############################################
#Next location keyframe duplication operator
#############################################
class TRANSFORM_OT_rtmanim_keyframe_insert_next_location(bpy.types.Operator):
    bl_label = "Duplicate next location keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_next_location"
    bl_description = "Duplicate next location keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'location', 'next')
        return {'FINISHED'}

#################################################
#Previous rotation keyframe duplication operator
#################################################
class TRANSFORM_OT_rtmanim_keyframe_insert_prev_rotation(bpy.types.Operator):
    bl_label = "Duplicate previous rotation keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_prev_rotation"
    bl_description = "Duplicate previous rotation keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'r', 'prev')
        return {'FINISHED'}

#############################################
#Next rotation keyframe duplication operator
#############################################
class TRANSFORM_OT_rtmanim_keyframe_insert_next_rotation(bpy.types.Operator):
    bl_label = "Duplicate next rotation keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_next_rotation"
    bl_description = "Duplicate next rotation keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'r', 'next')
        return {'FINISHED'}

##############################################
#Previous scale keyframe duplication operator
##############################################
class TRANSFORM_OT_rtmanim_keyframe_insert_prev_scale(bpy.types.Operator):
    bl_label = "Duplicate previous scale keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_prev_scale"
    bl_description = "Duplicate previous scale keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'scale', 'prev')
        return {'FINISHED'}

##########################################
#Next scale keyframe duplication operator
##########################################
class TRANSFORM_OT_rtmanim_keyframe_insert_next_scale(bpy.types.Operator):
    bl_label = "Duplicate next scale keyframe"
    bl_idname = "transform.rtmanim_keyframe_insert_next_scale"
    bl_description = "Duplicate next scale keyframe"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context): return True
    def execute(self, context):
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
        keyframe_insert(context, 'scale', 'next')
        return {'FINISHED'}

###############################################################################################
#Modal operator with keyframe selecting/deselecting/erasing logic, uses a singleton modal loop
###############################################################################################
class TRANSFORM_OT_rtmanim_modal_keyframe_sel(bpy.types.Operator):
    bl_label = "real time animation operator"
    bl_idname = "transform.rtmanim_modal_keyframe_sel"
    bl_description = "real time animation operator"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return True

    #operator control
    op_running=None
    @classmethod
    def stop(cls):
        cls.op_running=False
        cls.anim_data_paths_actions.clear()
        #deactivate buttons
        TRANSFORM_OT_rtmanim_keyframe_sel_location.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_sel_rotation.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_sel_scale.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_dsel_location.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_dsel_rotation.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_dsel_scale.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_del_location.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_del_rotation.deactivate()
        TRANSFORM_OT_rtmanim_keyframe_del_scale.deactivate()

    #controls
    objects=None
    frame_remembered=None
    initial_timer_after_mouse_press=None
    anim_data_paths_actions=dict()
    sel_fcurves=list() #fcurves for selecting keyframes
    dsel_fcurves=list() #fcurves for deselecting keyframes
    del_data_paths=list() #deletion is done differently than selecting/deselecting
    @classmethod
    def add_anim_data_path_action(cls, anim_data_path, action):
        if anim_data_path=='r': 
            cls.anim_data_paths_actions['rotation_quaternion'] = action
            cls.anim_data_paths_actions['rotation_euler'] = action
            cls.anim_data_paths_actions['rotation_axis_angle'] = action
        else: cls.anim_data_paths_actions[anim_data_path] = action
    @classmethod
    def remove_anim_data_path(cls, anim_data_path):
        try:
            if anim_data_path=='r': 
                cls.anim_data_paths_actions.pop('rotation_quaternion')
                cls.anim_data_paths_actions.pop('rotation_euler')
                cls.anim_data_paths_actions.pop('rotation_axis_angle')
            else: cls.anim_data_paths_actions.pop(anim_data_path)
        except: pass
        if len(cls.anim_data_paths_actions) < 1: cls.stop()

    ##################################################################
    #method for selecting/deselecting keyframes for the input fcurves
    ##################################################################
    @classmethod
    def sel_dsel_keyframes(cls, fcurves, curframe, frame_remembered, action):
        value = True if action=='s' else False
        for fc in fcurves:
            #check if fcurve has keyframes
            if len(fc.keyframe_points)<1: continue

            ################################
            #if time slider is moving right
            ################################
            if curframe > frame_remembered:                
                #get index of current frame
                index_curframe = keyframe_search(fc.keyframe_points, curframe)[0]
                #get index of remembered frame
                index_frame_remembered = keyframe_search(fc.keyframe_points, frame_remembered)
                (val1, val2) = index_frame_remembered[1:3]
                index_frame_remembered = val1 if val1!=None else val2
                #get keyframes between the indices
                if index_curframe==None or index_frame_remembered==None: continue
                keyframes = fc.keyframe_points[index_frame_remembered:index_curframe+1]

            ###############################
            #if time slider is moving left
            ###############################
            else:
                #get index of current frame
                index_curframe = keyframe_search(fc.keyframe_points, curframe)[2]
                #get index of remembered frame
                index_frame_remembered = keyframe_search(fc.keyframe_points, frame_remembered)
                (val1, val2) = index_frame_remembered[0:2]
                index_frame_remembered = val2 if val2!=None else val1
                #get keyframes between the indices
                if index_curframe==None or index_frame_remembered==None: continue
                keyframes = fc.keyframe_points[index_curframe:index_frame_remembered+1]

            #select/deselect keyframes
            for kf in keyframes:
                kf.select_control_point = value
                kf.select_left_handle = value
                kf.select_right_handle = value

    def invoke(self, context, event):
        cls = self.__class__

        #inits
        if len(context.selected_objects) < 1: return {'CANCELLED'} #no selected objects
        cls.objects = context.selected_pose_bones if context.mode=='POSE' else context.selected_objects
        cls.frame_remembered = context.scene.frame_current
        cls.initial_timer_after_mouse_press = False

        #get fcurves for selecting/deselecting keyframes, make sure to use context.selected_objects
        #as the argument and not cls.objects, since cls.objects can be selected pose bones.
        fcurves = get_fcurves(context, context.selected_objects, cls.anim_data_paths_actions, ('s', 'd'))
        cls.sel_fcurves = fcurves['s']
        cls.dsel_fcurves = fcurves['d']
        #get actions for erasing (deleting) keyframes
        cls.del_data_paths = list()
        for (data_path, action) in cls.anim_data_paths_actions.items():
            if action=='e': cls.del_data_paths.append(data_path)

        #start modal loop, all this stuff must be at the end of invoke so above code can always run
        if cls.op_running: return {'FINISHED'}
        cls.op_running=True
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(.01, window=context.window)
        self._prev_time_duration = self._timer.time_duration
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        cls = self.__class__

        #######################
        #check if need to stop
        #######################
        cur_objects = context.selected_pose_bones if context.mode=='POSE' else context.selected_objects
        if cls.op_running!=True or cls.objects!=cur_objects:
            cls.stop() #to deactivate in cases like when user changes object selection
            try: context.window_manager.event_timer_remove(self._timer)
            except: pass
            return {'FINISHED'}

        if event.type=='LEFTMOUSE' and event.value=="PRESS":
            cls.initial_timer_after_mouse_press = True

        elif event.type=='TIMER' and self._prev_time_duration!=self._timer.time_duration:
            self._prev_time_duration=self._timer.time_duration
            
            #check if this is the first timer after a mouse press event
            if cls.initial_timer_after_mouse_press:
                cls.frame_remembered = context.scene.frame_current
                cls.initial_timer_after_mouse_press = False

            #don't do anything if time slider is staying in same place
            if cls.frame_remembered==context.scene.frame_current: pass

            #below applies when user is moving the time slider
            else:
                curframe = context.scene.frame_current

                ###########################
                #select/deselect keyframes
                ###########################
                cls.sel_dsel_keyframes(cls.sel_fcurves, curframe, cls.frame_remembered, 's')
                cls.sel_dsel_keyframes(cls.dsel_fcurves, curframe, cls.frame_remembered, 'd')

                ##################
                #delete keyframes
                ##################
                for keyframe_data_path in cls.del_data_paths:
                    for obj in cls.objects:
                        for frm in range(cls.frame_remembered, curframe, (-1 if cls.frame_remembered>curframe else 1)):
                            try: obj.keyframe_delete(data_path=keyframe_data_path, frame=frm)
                            except: pass
                            
                cls.frame_remembered = curframe

        #keep modal loop going
        return {'PASS_THROUGH'}

#############################
#Location keyframe selecting
#############################
class TRANSFORM_OT_rtmanim_keyframe_sel_location(bpy.types.Operator):
    bl_label = "Select location keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_sel_location"
    bl_description = "Select location keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('location', 's')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_location.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_location.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('location')
            cls.deactivate()
        return {'FINISHED'}

#############################
#Rotation keyframe selecting
#############################
class TRANSFORM_OT_rtmanim_keyframe_sel_rotation(bpy.types.Operator):
    bl_label = "Select rotation keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_sel_rotation"
    bl_description = "Select rotation keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('r', 's')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_rotation.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_rotation.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('r')
            cls.deactivate()
        return {'FINISHED'}

##########################
#Scale keyframe selecting
##########################
class TRANSFORM_OT_rtmanim_keyframe_sel_scale(bpy.types.Operator):
    bl_label = "Select scale keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_sel_scale"
    bl_description = "Select scale keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('scale', 's')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_scale.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_scale.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('scale')
            cls.deactivate()
        return {'FINISHED'}

###############################
#Location keyframe deselecting
###############################
class TRANSFORM_OT_rtmanim_keyframe_dsel_location(bpy.types.Operator):
    bl_label = "Deselect location keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_dsel_location"
    bl_description = "Deselect location keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('location', 'd')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_location.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_location.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('location')
            cls.deactivate()
        return {'FINISHED'}

###############################
#Rotation keyframe deselecting
###############################
class TRANSFORM_OT_rtmanim_keyframe_dsel_rotation(bpy.types.Operator):
    bl_label = "Deselect rotation keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_dsel_rotation"
    bl_description = "Deselect rotation keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('r', 'd')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_rotation.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_rotation.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('r')
            cls.deactivate()
        return {'FINISHED'}

############################
#Scale keyframe deselecting
############################
class TRANSFORM_OT_rtmanim_keyframe_dsel_scale(bpy.types.Operator):
    bl_label = "Deselect scale keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_dsel_scale"
    bl_description = "Deselect scale keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('scale', 'd')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_scale.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_del_scale.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('scale')
            cls.deactivate()
        return {'FINISHED'}

######################################
#Location keyframe erasing (deleting)
######################################
class TRANSFORM_OT_rtmanim_keyframe_del_location(bpy.types.Operator):
    bl_label = "Delete location keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_del_location"
    bl_description = "Delete location keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('location', 'e')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_location.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_location.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('location')
            cls.deactivate()
        return {'FINISHED'}

###########################
#Rotation keyframe erasing
###########################
class TRANSFORM_OT_rtmanim_keyframe_del_rotation(bpy.types.Operator):
    bl_label = "Delete rotation keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_del_rotation"
    bl_description = "Delete rotation keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('r', 'e')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_rotation.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_rotation.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('r')
            cls.deactivate()
        return {'FINISHED'}

########################
#Scale keyframe erasing
########################
class TRANSFORM_OT_rtmanim_keyframe_del_scale(bpy.types.Operator):
    bl_label = "Delete scale keyframes with time slider"
    bl_idname = "transform.rtmanim_keyframe_del_scale"
    bl_description = "Delete scale keyframes with time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop() #stop LRS
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.add_anim_data_path_action('scale', 'e')
            rval = bpy.ops.transform.rtmanim_modal_keyframe_sel('INVOKE_DEFAULT')
            if 'CANCELLED' not in rval: cls.activate()
            TRANSFORM_OT_rtmanim_keyframe_sel_scale.deactivate()
            TRANSFORM_OT_rtmanim_keyframe_dsel_scale.deactivate()
        else:
            TRANSFORM_OT_rtmanim_modal_keyframe_sel.remove_anim_data_path('scale')
            cls.deactivate()
        return {'FINISHED'}

################################################################
#Operator with keyframe info logic, uses a singleton modal loop
################################################################
class TRANSFORM_OT_rtmanim_modal_info_logic(bpy.types.Operator):
    bl_label = "real time animation operator"
    bl_idname = "transform.rtmanim_modal_info_logic"
    bl_description = "real time animation operator"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return True

    #operator control
    op_running=None
    @classmethod
    def stop(cls):
        cls.op_running=False
        #deactivate button
        TRANSFORM_OT_rtmanim_info.deactivate()

    def invoke(self, context, event):
        cls = self.__class__
        self._timer_counter=0

        #start modal loop, all this stuff must be at the end of invoke
        if cls.op_running: return {'FINISHED'}
        cls.op_running=True
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(.2, window=context.window)
        self._prev_time_duration = self._timer.time_duration
        return {'RUNNING_MODAL'}  

    def modal(self, context, event):
        cls = self.__class__

        #######################
        #check if need to stop
        #######################
        if cls.op_running!=True:
            context.scene.rtmanim_keyframe_info_property=''
            for areas in bpy.context.screen.areas: areas.tag_redraw()
            try: context.window_manager.event_timer_remove(self._timer)
            except: pass
            return {'FINISHED'}
        
        if event.type=='TIMER' and self._prev_time_duration!=self._timer.time_duration:
            self._prev_time_duration=self._timer.time_duration

            curframe = context.scene.frame_current
            context.scene.rtmanim_keyframe_info_property=''
            info_dict = dict()

            ##############################################################
            #in pose mode, display info only for currently selected bones
            ##############################################################
            if context.mode=='POSE':
                for b in context.selected_pose_bones: info_dict[b.name]=list()
                #get all fcurves for the currently selected bones
                fcurves = get_fcurves(context, context.selected_objects, None, ['i'])['i']
                for fc in fcurves:
                    if keyframe_search(fc.keyframe_points, curframe)[1]==None: continue #no current keyframe
                    bone_name = (fc.data_path.split('["')[1]).split('"]')[0]
                    anim_data_path = fc.data_path.split('.')[-1]
                    cur_info = info_dict[bone_name]
                    if anim_data_path not in cur_info: info_dict[bone_name].append(anim_data_path)

            #####################################################
            #object mode, go over all currently selected objects
            #####################################################
            else:
                for obj in context.selected_objects: 
                    try: fcurves = obj.animation_data.action.fcurves; fcurves[0]
                    except: continue #no animation data
                    info_dict[obj.name]=list()
                    for fc in fcurves:
                        if obj.type=='ARMATURE' and '[' in fc.data_path: continue #skip bone fcurves
                        if keyframe_search(fc.keyframe_points, curframe)[1]==None: continue #no current keyframe
                        anim_data_path = fc.data_path.split('.')[-1]
                        cur_info = info_dict[obj.name]
                        if anim_data_path not in cur_info: info_dict[obj.name].append(anim_data_path)

            ############################################
            #output info strings as one combined string
            ############################################
            if len(info_dict)==1: 
                combined_list=list(info_dict.values())[0]
                context.scene.rtmanim_keyframe_info_property = ', '.join(combined_list)
            elif len(info_dict)>1:
                combined_list=list()
                for (name, info_list) in info_dict.items():
                    if len(info_list)>0:
                        combined_list.append(''.join(('(',name,') ')))
                        for item in info_list: combined_list.extend((item, ', '))
                        combined_list[-1]='  ' #spacing between info for different objects/bones
                context.scene.rtmanim_keyframe_info_property = ''.join(combined_list)
            #update blender gui
            for area in bpy.context.screen.areas: area.tag_redraw()

        return {'PASS_THROUGH'}

########################
#Keyframe info operator
########################
class TRANSFORM_OT_rtmanim_info(bpy.types.Operator):
    bl_label = "Show info about keyframes under the time slider"
    bl_idname = "transform.rtmanim_info"
    bl_description = "Show info about keyframes under the time slider"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            bpy.ops.transform.rtmanim_modal_info_logic('INVOKE_DEFAULT')
            cls.activate()
        else:
            TRANSFORM_OT_rtmanim_modal_info_logic.stop()
            cls.deactivate()
        return {'FINISHED'}

#################################################################
#Operator with smooth follow logic. Uses a singleton modal loop.
#################################################################
class TRANSFORM_OT_rtmanim_modal_smooth_follow_logic(bpy.types.Operator):
    bl_label = "real time animation operator"
    bl_idname = "transform.rtmanim_modal_smooth_follow_logic"
    bl_description = "real time animation operator"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return True

    #operator control
    op_running=None
    @classmethod
    def stop(cls):
        cls.op_running=False
        #deactivate button
        TRANSFORM_OT_rtmanim_smooth_follow.deactivate()
        
    #various controls
    active_or_not=None
    dir_unit_vector=None
    objects=None

    def invoke(self, context, event):
        cls = self.__class__
        cls.active_or_not = False

        #start modal loop, all this stuff must be at the end of invoke so above code can always run
        if cls.op_running: return {'FINISHED'}
        cls.op_running=True
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(.01, window=context.window)
        self._prev_time_duration = self._timer.time_duration
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        cls=self.__class__

        #######################
        #check if need to stop
        #######################
        if cls.op_running!=True:
            try: context.window_manager.event_timer_remove(self._timer)
            except: pass
            return {'FINISHED'}

        if event.type=='LEFT_CTRL' and event.value=='PRESS':
            #user input direction vector, uses local coords for each object
            cls.dir_unit_vector = Vector((float(context.scene.rtmanim_smooth_follow_x_property),
                float(context.scene.rtmanim_smooth_follow_y_property), float(context.scene.rtmanim_smooth_follow_z_property)))
            cls.dir_unit_vector.normalize()
            #get selected objects
            if context.mode=='POSE': cls.objects = context.selected_pose_bones
            else: cls.objects = context.selected_objects
            #set active
            cls.active_or_not = not cls.active_or_not

        elif event.type=='MOUSEMOVE':
            #below variables are used locally by the modal function
            self._mouse_region_x = event.mouse_region_x
            self._mouse_region_y = event.mouse_region_y
  
        elif event.type=='TIMER' and self._prev_time_duration!=self._timer.time_duration:
            self._prev_time_duration=self._timer.time_duration

            #check if active
            if cls.active_or_not != True:
                return {'PASS_THROUGH'}
                
            #move objects
            for obj in cls.objects:
                #useful variables
                if context.mode=='POSE': total_matrix = context.selected_objects[0].matrix_world @ obj.matrix
                else: total_matrix = obj.matrix_world
                total_inv_q = total_matrix.to_quaternion().inverted()
                #object local space transformation, origin_vector is a world space vector pointing to object's pivot
                origin_vector = total_matrix @ Vector((0,0,0))
                location3d = region_2d_to_location_3d(context.region, context.space_data.region_3d,
                    (self._mouse_region_x, self._mouse_region_y), origin_vector)
                
                #############
                #translation
                #############
                if obj.rotation_mode[0]=='Q': 
                    current_quaternion = obj.rotation_quaternion.normalized()
                elif obj.rotation_mode[0]=='A': 
                    #current_quaternion = Quaternion(obj.rotation_axis_angle)
                    #above line doesn't do what's needed, so have to use the below
                    obj.rotation_mode='QUATERNION'
                    current_quaternion = obj.rotation_quaternion.normalized()
                    obj.rotation_mode = 'AXIS_ANGLE'
                else: current_quaternion = obj.rotation_euler.to_quaternion()
                #Below vector is in object's modified coord system. Note, (location3d-origin_vector) is in world coords.
                location_difference_vector = current_quaternion @ total_inv_q @ (location3d-origin_vector)
                #move by percentage of distance
                obj.location += location_difference_vector*context.scene.rtmanim_smooth_follow_factor_property/100.0

                ########################################################
                #rotation, calculated in object's modified coord system
                ########################################################
                if location_difference_vector.magnitude > 0.01 and cls.dir_unit_vector.magnitude > 0:
                    #get object's current direction vector, find additional quaternion rotation needed, rotate the object
                    dir_unit_vector = current_quaternion @ cls.dir_unit_vector
                    extra_q = dir_unit_vector.rotation_difference(location_difference_vector)
                    #rotate the object, based on the rotation mode
                    if obj.rotation_mode[0]=='Q': 
                        obj.rotation_quaternion = (extra_q @ obj.rotation_quaternion).normalized()
                    elif obj.rotation_mode[0]=='A': 
                        #obj.rotation_axis_angle = (extra_q @ Quaternion(obj.rotation_axis_angle)).to_axis_angle()
                        #above line doesn't work and throws an exception, so have to use the below
                        obj.rotation_mode='QUATERNION'
                        obj.rotation_quaternion = (extra_q @ obj.rotation_quaternion).normalized()
                        obj.rotation_mode = 'AXIS_ANGLE'
                    else: obj.rotation_euler.rotate(extra_q)

        return {'PASS_THROUGH'}

########################
#Smooth follow operator
########################
class TRANSFORM_OT_rtmanim_smooth_follow(bpy.types.Operator):
    bl_label = "Make objects follow the mouse, use left Ctrl to start/pause"
    bl_idname = "transform.rtmanim_smooth_follow"
    bl_description = "Make objects follow the mouse, use left Ctrl to start/pause"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    active = False
    PIC_INACTIVE='BLANK1'
    PIC_ACTIVE='FILE_TICK'
    pic_shown=PIC_INACTIVE
    @classmethod
    def activate(cls):
        cls.active=True
        cls.pic_shown=cls.PIC_ACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()
    @classmethod
    def deactivate(cls):
        cls.active=False
        cls.pic_shown=cls.PIC_INACTIVE
        for areas in bpy.context.screen.areas: areas.tag_redraw()

    def execute(self, context):
        cls=self.__class__
        if not cls.active:
            TRANSFORM_OT_rtmanim_modal_info_logic.stop() #stop info
            bpy.ops.transform.rtmanim_modal_smooth_follow_logic('INVOKE_DEFAULT')
            cls.activate()
        else:
            TRANSFORM_OT_rtmanim_modal_smooth_follow_logic.stop()
            cls.deactivate()
        return {'FINISHED'}

###################
#Stop all operator
###################
class TRANSFORM_OT_rtmanim_stop_all(bpy.types.Operator):
    bl_label = "Deactivate all buttons"
    bl_idname = "transform.rtmanim_stop_all"
    bl_description = "Deactivate all buttons"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context): return True

    def execute(self, context):
        #make all modals stop and exit
        TRANSFORM_OT_rtmanim_modal_kf_and_tm.stop()
        TRANSFORM_OT_rtmanim_modal_keyframe_sel.stop()
        TRANSFORM_OT_rtmanim_modal_smooth_follow_logic.stop()
        TRANSFORM_OT_rtmanim_modal_info_logic.stop()
        return {'FINISHED'}

##############
#Registration
##############
def register():
    #classes
    bpy.utils.register_class(VIEW3D_PT_rtmanim_panel)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_modal_kf_and_tm)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_move)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_rotate)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_location)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_location)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_rotation)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_rotation)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_modal_keyframe_sel)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_sel_location)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_sel_rotation)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_sel_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_dsel_location)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_dsel_rotation)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_dsel_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_del_location)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_del_rotation)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_keyframe_del_scale)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_modal_smooth_follow_logic)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_smooth_follow)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_modal_info_logic)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_info)
    bpy.utils.register_class(TRANSFORM_OT_rtmanim_stop_all)
    #properties
    bpy.types.Scene.rtmanim_time_property = bpy.props.IntProperty(name="Pause", description="How long to pause before advancing current frame", min=0, default=0)
    bpy.types.Scene.rtmanim_lkeyframe_frequency_property = bpy.props.IntProperty(name="", description="Spacing between location keyframes", min=1, default=2)
    bpy.types.Scene.rtmanim_rkeyframe_frequency_property = bpy.props.IntProperty(name="", description="Spacing between rotation keyframes", min=1, default=2)
    bpy.types.Scene.rtmanim_skeyframe_frequency_property = bpy.props.IntProperty(name="", description="Spacing between scale keyframes", min=1, default=2)
    bpy.types.Scene.rtmanim_smooth_follow_factor_property = bpy.props.FloatProperty(name="Follow", description="How quickly to follow the mouse, 0 to 100", min=0, max=100, default=5)
    bpy.types.Scene.rtmanim_smooth_follow_x_property = bpy.props.FloatProperty(name="X", description="Direction vector X component", default=0.0)
    bpy.types.Scene.rtmanim_smooth_follow_y_property = bpy.props.FloatProperty(name="Y", description="Direction vector Y component", default=0.0)
    bpy.types.Scene.rtmanim_smooth_follow_z_property = bpy.props.FloatProperty(name="Z", description="Direction vector Z component", default=1.0)
    bpy.types.Scene.rtmanim_keyframe_info_property = bpy.props.StringProperty(name="", description="Keyframe info", default="")
def unregister():
    #classes
    bpy.utils.unregister_class(VIEW3D_PT_rtmanim_panel)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_modal_kf_and_tm)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_move)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_rotate)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_location)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_location)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_rotation)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_rotation)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_prev_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_insert_next_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_modal_keyframe_sel)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_sel_location)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_sel_rotation)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_sel_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_dsel_location)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_dsel_rotation)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_dsel_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_del_location)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_del_rotation)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_keyframe_del_scale)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_modal_smooth_follow_logic)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_smooth_follow)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_modal_info_logic)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_info)
    bpy.utils.unregister_class(TRANSFORM_OT_rtmanim_stop_all)
    #properties
    del bpy.types.Scene.rtmanim_time_property
    del bpy.types.Scene.rtmanim_lkeyframe_frequency_property
    del bpy.types.Scene.rtmanim_rkeyframe_frequency_property
    del bpy.types.Scene.rtmanim_skeyframe_frequency_property
    del bpy.types.Scene.rtmanim_smooth_follow_factor_property
    del bpy.types.Scene.rtmanim_smooth_follow_x_property
    del bpy.types.Scene.rtmanim_smooth_follow_y_property
    del bpy.types.Scene.rtmanim_smooth_follow_z_property
    del bpy.types.Scene.rtmanim_keyframe_info_property
if __name__ == '__main__':
    register()




