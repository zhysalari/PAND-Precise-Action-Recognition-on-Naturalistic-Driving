# -*- coding: utf-8 -*-
# @Time    : 2022/4/9 15:30
# @Author  : ycxia
# @File    : submit_zhy_new.py
# @Brief   : post process the results for three branches.

import os
import sys
import cv2
import time
import json
from pprint import pprint
from collections import defaultdict, OrderedDict
from scipy.optimize import linear_sum_assignment

import numpy as np
from copy import deepcopy
import matplotlib.pyplot as plt
import pickle
# Global parameters
AICITY_DATA_ROOT = '/raid/aicity/data/Aicity'
CLASSES = ['0:Normal Forward Driving',
'1:Drinking',
'2:Phone Call(right)',
'3:Phone Call(left)',
'4:Eating',
'5:Text (Right)',
'6:Text (Left)',
'7:Hair / makeup',
'8:Reaching behind',
'9:Adjust control panel',
'10:Pick up from floor (Driver)',
'11:Pick up from floor (Passenger)',
'12:Talk to passenger at the right',
'13:Talk to passenger at backseat',
'14:yawning',
'15:Hand on head',
'16:Singing with music',
'17:shaking or dancing with music']

cls_idxs=[0,6,5,7,8,1,2,3,9,12,13,11,10,4,15,14,16,17]#class index order
import random
random.seed(1234)

def randomcolor():
    colorArr = ['1','2','3','4','5','6','7','8','9','A','B','C','D','E','F']
    color = ""
    for i in range(6):
        color += colorArr[random.randint(0,14)]
    return "#"+color
def Hex_to_RGB(hex):
    r = int(hex[1:3],16)
    g = int(hex[3:5],16)
    b = int(hex[5:7], 16)
    rgb = np.array([r,g,b])
    # print(rgb)
    return rgb
color_map = np.array([Hex_to_RGB(randomcolor()) for i in range(18)])
color_map[0]=np.array([255,255,255])

def build_pose_txt(pkl_file, out_result):
    with open(pkl_file, 'rb') as f:
        data = pickle.load(f)
    pose_rst_dict = dict()
    for pose_results in data:
        video = pose_results['frame_dir'].split('__frame')[0]
        frame_begin = int(pose_results['frame_dir'].split('_frame')[1])
        if video not in pose_rst_dict.keys():
            pose_rst_dict[video] = []  # [frame_begin,pose_results['keypoint']]
        else:
            pose_rst_dict[video].append([frame_begin, pose_results['keypoint']])

    for key in pose_rst_dict.keys():
        pose_rst_dict[key].sort(key=lambda x: x[0])
    with open(out_result, 'w') as f:
        for video in pose_rst_dict.keys():
            for keypoints in pose_rst_dict[video]:
                begin_frame = keypoints[0]
                keypoints = keypoints[1][0]
                for i, keypoint in enumerate(keypoints):
                    f.writelines("{:s} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d}\n".format(video,
                                                                                                        begin_frame + i,
                                                                                                        int(keypoint[
                                                                                                                0, 0]),
                                                                                                        int(keypoint[
                                                                                                                0, 1]),
                                                                                                        int(keypoint[
                                                                                                                1, 0]),
                                                                                                        int(keypoint[
                                                                                                                1, 1]),
                                                                                                        int(keypoint[
                                                                                                                2, 0]),
                                                                                                        int(keypoint[
                                                                                                                2, 1]),
                                                                                                        int(keypoint[
                                                                                                                3, 0]),
                                                                                                        int(keypoint[
                                                                                                                3, 1]),
                                                                                                        int(keypoint[
                                                                                                                4, 0]),
                                                                                                        int(keypoint[
                                                                                                                4, 1])))

def link_tubes(data,
               MAX_INTERRUPTION = 4):
    # sliding_window = 16
    # sliding_window = 32
    # sliding_window = 48
    # MAX_INTERRUPTION = 4s
    all_proposals=dict()
    for cls in cls_idxs:
        score_threshold = np.sort(data[:,cls+1])[-200:].mean()*0.8#np.sort(data[:,cls+1]).mean()+bias[cls]#+bias[cls]
        print(CLASSES[cls],score_threshold)
        score_bar = data[:,cls+1].copy()
        init_pred_idxs = np.where(score_bar>score_threshold)[0]#prediction
        init_pred_idxs = np.sort(init_pred_idxs)
        last_clip_idx = -1#
        proposal=[]
        this_class_proposals=[]
        for this_clip_idx in init_pred_idxs:#
            this_clip = np.array([data[this_clip_idx, 0], cls, data[this_clip_idx, cls + 1]])
            if last_clip_idx == -1:#proposal is empty
                proposal.append(this_clip)
                last_clip_idx = this_clip_idx
                continue
            if this_clip_idx-last_clip_idx < MAX_INTERRUPTION*2:#
                proposal.append(this_clip)
                last_clip_idx = this_clip_idx
            else:
                this_class_proposals.append(deepcopy(proposal))
                proposal=[]
                proposal.append(this_clip)
                last_clip_idx = this_clip_idx
        # if len(proposal)>0 and len(this_class_proposals)>0 and proposal[-1][0]!=this_class_proposals[-1][0][0]:
        if len(proposal)>0:
            this_class_proposals.append(deepcopy(proposal))

        all_proposals[CLASSES[cls]]=deepcopy(this_class_proposals)
    return all_proposals



def post_link(all_proposals, max_interp_time=8, min_const_time=10, max_const_time=30):
    # second link
    print("Change.")
    for cls in cls_idxs[1:]:
        last_proposal = None
        # for i, proposals in enumerate(all_proposals[clsname]):
        #     print("{:s}-{:d}: {:03d}:{:03d}".format(clsname,i,int(proposals[0][0]),int(proposals[-1][1])))

        del_idx = []
        for i, proposal in enumerate(all_proposals[CLASSES[cls]]):
            if last_proposal is None:
                last_proposal = proposal
            else:
                if (proposal[0][0] <= last_proposal[-1][0] + max_interp_time * 8) and (
                        (proposal[-1][0] - last_proposal[0][0])  >= min_const_time* 8) and (
                        (proposal[-1][0] - last_proposal[0][0])  <= max_const_time* 8):
                    last_proposal += proposal
                    del_idx.append(i)
                else:
                    last_proposal = proposal
        del_idx.reverse()
        for i in del_idx:
            del all_proposals[CLASSES[cls]][i]

        # for i, proposals in enumerate(all_proposals[clsname]):
        #     print("{:s}-{:d}: {:03d}:{:03d}".format(clsname,i,int(proposals[0][0]),int(proposals[-1][1])))

    print("Done.")
    return all_proposals

def caculate_iou(stamps,begin,end):
    ious=[]
    for stamp in stamps:
        ious.append((min(end,stamp[1]*8)-max(begin,stamp[0]*8))/(max(end,stamp[1]*8)-min(begin,stamp[0]*8)))
    return ious

def cascade_filter(proposals, data,zhy_stamps, step, pwm_th, min_const_time=8,max_const_time=30):
    all_proposals = dict()
    data_new = data.copy()

    for cls in cls_idxs[1:]:
        max_idx=-1
        max_score=0
        del_idxs=[]
        if CLASSES[cls] not in proposals.keys():
            continue
        if len(proposals[CLASSES[cls]]) == 1:

            out_proposal = deepcopy(proposals[CLASSES[cls]][0])
            this_score_bar = data_new[int(out_proposal[0][0] // 4):int(out_proposal[-1][0] // 4),
                             cls + 1]  # np.array(proposal)[:,-1]
            proposal_score_thresh = 0.25 * this_score_bar.max() + 0.75 * this_score_bar.min()  # 0.25 * np.array(proposal)[:, 2].max() + 0.75 * np.array(proposal)[:, 2].min()

            proposal_score = this_score_bar.mean()
            if this_score_bar.max() - this_score_bar.min() <= 0.1:
                proposal_score_thresh *= 0.8  # this_score_bar.mean()
            # else:
            # this_score_bar = data_new[max(0,int(proposal[0][0]//step)):min(len(data_new)-1,int(proposal[-1][0]//step)),cls+1]
            # proposal_score_thresh = 0.25 * this_score_bar.max() + 0.75 * this_score_bar.min()#0.25 * np.array(proposal)[:, 2].max() + 0.75 * np.array(proposal)[:, 2].min()
            # proposal_score = data_new[(np.array(proposal)[:,0]//4).astype('int'),cls+1].mean()#np.array(proposal)[:,-1].mean()
            print(CLASSES[cls], (this_score_bar > proposal_score).mean(), proposal_score)
            indx = list(np.arange(1, 19))
            del indx[cls]
            data_new[int(out_proposal[0][0] // step):int(out_proposal[-1][0] // step), indx] = 0
            continue
    for cls in cls_idxs[1:]:
        max_idx=-1
        max_score=0
        del_idxs=[]
        if CLASSES[cls] not in proposals.keys():
            continue
        if len(proposals[CLASSES[cls]]) == 1:
            continue
        for idx,proposal in enumerate(proposals[CLASSES[cls]]):
            if len(proposal)==1:
                continue
            # if cls in [1,2,3]:
            this_score_bar = data_new[int(proposal[0][0] // 4):int(proposal[-1][0] // 4),
                             cls + 1]  # np.array(proposal)[:,-1]
            proposal_score_thresh = 0.25 * this_score_bar.max() + 0.75 * this_score_bar.min()  # 0.25 * np.array(proposal)[:, 2].max() + 0.75 * np.array(proposal)[:, 2].min()

            proposal_score = this_score_bar.mean()
            if this_score_bar.max()-this_score_bar.min() <= 0.1:
                proposal_score_thresh *= 0.8  # this_score_bar.mean()
            # else:
                # this_score_bar = data_new[max(0,int(proposal[0][0]//step)):min(len(data_new)-1,int(proposal[-1][0]//step)),cls+1]
                # proposal_score_thresh = 0.25 * this_score_bar.max() + 0.75 * this_score_bar.min()#0.25 * np.array(proposal)[:, 2].max() + 0.75 * np.array(proposal)[:, 2].min()
                # proposal_score = data_new[(np.array(proposal)[:,0]//4).astype('int'),cls+1].mean()#np.array(proposal)[:,-1].mean()
            print(CLASSES[cls],(this_score_bar>proposal_score_thresh).mean(),proposal_score)
            if (this_score_bar>proposal_score_thresh).mean()<pwm_th or ((proposal[-1][0]-proposal[0][0])//8<min_const_time) or ((proposal[-1][0]-proposal[0][0])//8>max_const_time) :#占空比小于阈值，则认为不置信len(proposal)/((proposal[-1][0]-proposal[0][0])//step)<pwm_th or
                del_idxs.insert(0,[idx, proposal_score])
            else:
                if (proposal_score >= max_score):
                    max_score = proposal_score
                    max_idx = idx
        if max_idx!=-1:
            out_proposal=deepcopy(proposals[CLASSES[cls]][max_idx])
            indx = list(np.arange(1, 19))
            del indx[cls]
            data_new[int(out_proposal[0][0] // step):int(out_proposal[-1][0] // step), indx] = 0
            proposals[CLASSES[cls]] = [out_proposal]
        else:
            proposals[CLASSES[cls]] = []
    return proposals

def modify_margin(proposals,data ,zhy_stamps,step):
    all_proposals = dict()
    data_new = data.copy()
    for cls in cls_idxs[1:]:
        if cls in [0,]:#1,2,3,4,5,6,7,8,9,10,11,12,14
            continue
        max_idx = -1
        max_score = 0
        del_idxs = []
        for idx, proposal in enumerate(proposals[CLASSES[cls]]):
            if len(proposal) == 1:
                continue
            begin = proposal[0][0]
            end = proposal[-1][0]
            ious = caculate_iou(zhy_stamps, begin, end)
            ind = np.argmax(ious)
            if ious[ind] > 0.1:
                if int(zhy_stamps[ind][0]) != proposal[0][0] // 8:
                    proposal.insert(0, np.array([int(zhy_stamps[ind][0] * 8 -8), cls,
                                                 data_new[int(zhy_stamps[ind][0] * 8 // 4), cls + 1]]))
                if int(zhy_stamps[ind][1]) != proposal[-1][0] // 8:
                    proposal.append(np.array([int(zhy_stamps[ind][1] * 8 -8), cls,
                                              data_new[int(zhy_stamps[ind][1] * 8 // 4), cls + 1]]))
    return proposals


def filter_proposals(all_proposals,
                     min_const_time = [4,30],
                     TOP_K=1):
    filtered_proposals=dict()

    for cls in cls_idxs:
        clsname=CLASSES[cls]
        filtered_proposals[clsname]=[]
        temp_proposals=[]
        if clsname not in all_proposals.keys():
            continue
        for i, proposal in enumerate(all_proposals[clsname]):
            array_proposal = np.array(proposal)
            out = [array_proposal[0][0], array_proposal[-1][0], array_proposal[:, 2].mean(),i,len(proposal),(array_proposal[-1][0]-array_proposal[0][0] )/8] ###TODO 得分计算还有待完善，没有考虑中间未识别出的帧的影响

            if ((out[1] - out[0]) / 8 >= min_const_time[0]) and ((out[1] - out[0]) / 8 <= min_const_time[1]):
                temp_proposals.append(out)
            # elif len(all_proposals[clsname])==1:
            #     temp_proposals.append(out)
        if len(temp_proposals) == 0:
            continue
        temp_proposals.sort(key=lambda x: x[2],reverse= True)
        idx_maintain = [x[3] for x in temp_proposals[0:min(len(temp_proposals),TOP_K)]]
        filtered_proposals[clsname]=[all_proposals[clsname][i] for i in idx_maintain]
        # print(filtered_proposals[clsname])
    return filtered_proposals

def show_time_bar(filtered_proposals,labels=None,
                  width = 10,
                  k=1,
                  step=4,
                  cls_num=len(CLASSES),
                  N_f =100,video='',mark=False):
    """
    visualize results
    :param filtered_proposals:
    :param width:
    :param k:
    :param step:
    :param cls_num:
    :param N_f:
    :return:
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib import rcParams

    plt.figure(dpi=300)
    out_mat=np.zeros(((cls_num+1)*width,N_f,3),dtype='uint8')+255
    if labels is not None:
        out_mat[0:width,:]=color_map[labels]
        for i in range(cls_num):
            idx=np.where(labels==i)[0]
            if len(idx):
                plt.text(idx.min()+5,0, ''.join(str(i)))
    for i in range(cls_num):
        if i>=(cls_num/2+1):
            plt.text(N_f//3+N_f//6, (cls_num+12)*width+i%(cls_num/2+1)*23, CLASSES[i],color=color_map[i]/255)
        else:
            plt.text( N_f //100 , (cls_num + 12) * width +  (i-1)% (cls_num / 2+1) * 23, CLASSES[i],
                     color=color_map[i] / 255)
    # plt.imshow(out_mat)
    for i, clsname in enumerate(CLASSES):
        if clsname in filtered_proposals.keys():
            for j, proposal in enumerate(filtered_proposals[clsname]):
                array_proposal = np.array(proposal)
                if i !=0 and mark:
                    plt.text(int(array_proposal[0][0]//step)+ 5, (i+1)*width, ''.join(str(i)))
                out_mat[(i+1)*width:(i+2)*width,int(array_proposal[0][0]//step): int(array_proposal[-1][0]//step)]=color_map[i]#给热力图置位
    plt.imshow(out_mat)
    plt.text(N_f/2-len(video)*8, -50,video)
    plt.yticks([])#list(np.arange(1,19,2)*width-width/2),list(np.arange(1,19,2))
    plt.xticks(list(np.arange(0,N_f,200)),list(np.arange(0,N_f,200)/step))
    plt.xlabel('time/s')
    plt.show()
    return

def processes_single_video_id(results_root,
                              multi_videos,
                              post='_latest_results_halfs',
                              step=4,
                              show=False,
                              outprint=False):
    """
    :param results_root:
    :param multi_videos:
    :param post:
    :param step:
    :param show:
    :param outprint:
    :return:
    """
    data1=np.loadtxt(os.path.join(results_root, multi_videos[0].split('.')[0])+post+'.txt')
    data2=np.loadtxt(os.path.join(results_root, multi_videos[1].split('.')[0])+post+'.txt')
    data3=np.loadtxt(os.path.join(results_root, multi_videos[2].split('.')[0])+post+'.txt')

    # CLASSES = list(range(1, len(Index_Action) + 1))
    N_f = min(len(data1),len(data2),len(data3))
    data = (data1[0:N_f]+data2[0:N_f]+data3[0:N_f])/3#data3[0:N_f]

    result = np.vstack([data[:,0],np.argmax(data[:,1:-2],axis=1),np.max(data[:,1:-2],axis=1)]).transpose()
    result = result[result[:,2]>0.3]
    all_proposals = (link_tubes(result, 16, debug=False))
    all_proposals = post_link(all_proposals)
    filtered_proposals = filter_proposals(all_proposals)
    if show:
        show_time_bar(filtered_proposals,step=step,N_f=N_f)

    if outprint:
        print("\nFiltered results are as following...\n")
        for clsname in CLASSES:
            for i, proposal in enumerate(filtered_proposals[clsname]):
                array_proposal = np.array(proposal)
                out = [array_proposal[0][0], array_proposal[-1][1], array_proposal[:, 2].mean(),i,len(proposal)*step] ###TODO 得分计算还有待完善，没有考虑中间未识别出的帧的影响
                print(
                    "{:s}-{:d}: {:03d}:{:03d}, {:02d}:{:02d}.{:02d}--{:02d}:{:02d}.{:02d}, {:02d}:{:02d}.{:02d}, {:.4f},  {:d}/{:d}".format(
                        clsname, i, int(out[0]), int(out[1]),
                        int(out[0] / 8 // 60),
                        int(out[0] / 8 % 60),
                        int((out[0] / 8 % 60 - int(out[0] / 8 % 60)) * 100),
                        int(out[1] / 8 // 60),
                        int(out[1] / 8 % 60),
                        int((out[1] / 8 % 60 - int(out[1] / 8 % 60)) * 100),
                        int((out[1] - out[0]) / 8 // 60),
                        int((out[1] - out[0]) / 8 % 60),
                        int(((out[1] - out[0]) / 8 % 60 - int(
                            (out[1] - out[0]) / 8 % 60)) * 100),
                        out[2], len(proposal)*step,
                        int(out[1] - out[0])))
    return filtered_proposals


def confusion_matrix(y_pred, y_real, normalize=None):
    """Compute confusion matrix.

    Args:
        y_pred (list[int] | np.ndarray[int]): Prediction labels.
        y_real (list[int] | np.ndarray[int]): Ground truth labels.
        normalize (str | None): Normalizes confusion matrix over the true
            (rows), predicted (columns) conditions or all the population.
            If None, confusion matrix will not be normalized. Options are
            "true", "pred", "all", None. Default: None.

    Returns:
        np.ndarray: Confusion matrix.
    """
    if normalize not in ['true', 'pred', 'all', None]:
        raise ValueError("normalize must be one of {'true', 'pred', "
                         "'all', None}")

    if isinstance(y_pred, list):
        y_pred = np.array(y_pred)
    if not isinstance(y_pred, np.ndarray):
        raise TypeError(
            f'y_pred must be list or np.ndarray, but got {type(y_pred)}')
    if not y_pred.dtype == np.int64:
        raise TypeError(
            f'y_pred dtype must be np.int64, but got {y_pred.dtype}')

    if isinstance(y_real, list):
        y_real = np.array(y_real)
    if not isinstance(y_real, np.ndarray):
        raise TypeError(
            f'y_real must be list or np.ndarray, but got {type(y_real)}')
    if not y_real.dtype == np.int64:
        raise TypeError(
            f'y_real dtype must be np.int64, but got {y_real.dtype}')

    label_set = np.unique(np.concatenate((y_pred, y_real)))
    num_labels = len(label_set)
    max_label = label_set[-1]
    label_map = np.zeros(max_label + 1, dtype=np.int64)
    for i, label in enumerate(label_set):
        label_map[label] = i

    y_pred_mapped = label_map[y_pred]
    y_real_mapped = label_map[y_real]

    confusion_mat = np.bincount(
        num_labels * y_real_mapped + y_pred_mapped,
        minlength=num_labels**2).reshape(num_labels, num_labels)

    with np.errstate(all='ignore'):
        if normalize == 'true':
            confusion_mat = (
                confusion_mat / confusion_mat.sum(axis=1, keepdims=True))
        elif normalize == 'pred':
            confusion_mat = (
                confusion_mat / confusion_mat.sum(axis=0, keepdims=True))
        elif normalize == 'all':
            confusion_mat = (confusion_mat / confusion_mat.sum())
        confusion_mat = np.nan_to_num(confusion_mat)

    return confusion_mat

def timecvt(str):
    """
    param str: time'x:xx:xx'
    return: represent in second
    """
    return float(int(str.split(':')[-2])*60+int(str.split(':')[-1]))

def load_gt(step, label_json, video, N_f, classnum):
    def load_json_file(file):
        import json
        with open(file, "r") as f:
            dicts = json.load(f)
        return dicts
    dict = load_json_file(label_json)
    labels = np.zeros((N_f),dtype='int64')
    mask = np.zeros((N_f),dtype='bool')
    time_stamps={}
    for cls in dict[video.lower()]:
        begin = timecvt(dict[video.lower()][cls]['begin'])
        end = timecvt(dict[video.lower()][cls]['end'])
        # one_hot[int(begin*8//step):int(end*8//step),int(cls)]=1
        labels[int(begin*8//step):int(end*8//step)]=int(cls)
        mask[int(begin*8//step):int(end*8//step)]=True
        time_stamps[CLASSES[int(cls)]] = [begin,end]
    return labels, mask, time_stamps

def mean_class_accuracy(in1, labels):
    """Calculate mean class accuracy.

    Args:
        scores (list[np.ndarray]): Prediction scores for each class.
        labels (list[int]): Ground truth labels.

    Returns:
        np.ndarray: Mean class accuracy.
    """
    if len(in1.shape)>1:
        pred = np.argmax(in1, axis=1)
    else:
        pred = in1
    cf_mat = confusion_matrix(pred, labels).astype(float)

    cls_cnt = cf_mat.sum(axis=1)
    cls_hit = np.diag(cf_mat)
    print(cf_mat)
    print("Precision:")
    class_p=[]
    for i in range(len(cf_mat)):
        class_p.append(cf_mat[i, i] / cf_mat[:, i].sum())
        print(f"class_{i:d} : {class_p[-1]:.03f}")
    print("mean_class_precision(No class 0): {:.4f}".format(np.mean(np.nan_to_num(class_p[0:]))))
    print("\nRecall:")
    class_r=[]
    for i in range(len(cf_mat)):
        class_r.append(cf_mat[i, i] / cf_mat[i, :].sum())
        print(f"class_{i:d} : {class_r[-1]:.03f}")
    print("mean_class_recall(No class 0): {:.4f}".format(np.mean(class_r[0:])))
    class_acc = [hit / cnt if cnt else 0.0 for cnt, hit in zip(cls_cnt, cls_hit)]


    mean_class_acc = np.mean(class_acc[1:])

    return mean_class_acc

def filter_multi_out(proposals,N_f):
    filtered_proposals = dict()
    mask=np.zeros(N_f)
    for cls in [5,6]:
        clsname = CLASSES[cls]
        filtered_proposals[clsname] = []
        temp_proposals = []
        if clsname not in proposals.keys():
            continue
        for i, proposal in enumerate(proposals[clsname]):
            array_proposal = np.array(proposal)
            out = [array_proposal[0][0], array_proposal[-1][0], array_proposal[:, 2].mean(), i, len(proposal),
                   (array_proposal[-1][0] - array_proposal[0][0]) / 8]
            if mask[int(out[0]//4):int(out[1]//4)].max()==0:
                mask[int(out[0]//4):int(out[1]//4)]=int(clsname.split(':')[0])
            else:
                clsname1 = CLASSES[int(mask[int(out[0]//4):int(out[1]//4)].max())]
                clsname2 = clsname
                start1, end1 = proposals[clsname1][0][0][0], proposals[clsname1][0][-1][0]
                start2, end2 = proposals[clsname2][0][0][0], proposals[clsname2][0][-1][0]
                if (min(end1, end2) - max(start1, start2)) / (max(end1, end2) - min(start1, start2))>0.8:
                    proposals[clsname1] = []
                    proposals[clsname2] = []
                continue

        # print(filtered_proposals[clsname])
    return proposals

def proposals_trans(proposals, N_f):
    pred = np.zeros(N_f,dtype='int64')
    for clsname in CLASSES:
        for i, proposal in enumerate(proposals[clsname]):
            array_proposal = np.array(proposal)
            out = [array_proposal[0][0], array_proposal[-1][0]]
            pred[int(out[0]//4):int(out[1]//4)]=int(clsname.split(':')[0])
    return pred

def add_cellphone(data,video,T=False):
    """
    :param data:
    :return:
    """
    if T:
        with open(os.path.join(AICITY_DATA_ROOT,'pose','A1_pose.txt'), 'r') as f:
            poses = f.readlines()  # r'W:\aicity/aicity1/A1'
        results_root = os.path.join(AICITY_DATA_ROOT,'cellphone_detect/A1')
    else:
        # if video.startswith('Dashboard_User_id_72519'):
        #     return data
        with open(os.path.join(AICITY_DATA_ROOT,'pose','A2_pose.txt'), 'r') as f:
            poses = f.readlines() # r'W:\aicity/aicity1/A1'
        results_root = os.path.join(AICITY_DATA_ROOT,'cellphone_detect/A2')

    pose_dict = dict()

    for pose in poses:
        pose = pose.split('\n')[0]
        pose = pose.split(' ')
        videoid = pose[0]
        frame_id = pose[1]
        keypoints = [
                     [int(pose[2]), int(pose[3])],
                     [int(pose[4]), int(pose[5])],
                     [int(pose[6]), int(pose[7])],
                     [int(pose[8]), int(pose[9])],
                     [int(pose[10]), int(pose[11])]]
        if videoid not in pose_dict.keys():
            pose_dict[videoid]=dict()
        pose_dict[videoid][frame_id]=keypoints

    result_file = 'modify_'+video+'_cellphone_results.txt'
    # print(video)
    with open(os.path.join(results_root,result_file),'r') as f:
        results = f.readlines()
    img = None
    last_left = -1
    last_right = -1
    for rst in results:
        rst = rst.split('\n')[0]
        rst = rst.split(' ')

        frame_id = int(rst[0])
        bbox = [int(x) for x in rst[1:5]]
        score = float(rst[5])
        if str(frame_id) in pose_dict[video].keys():
            nose = pose_dict[video][str(frame_id)][0]
            eyes = [pose_dict[video][str(frame_id)][1],pose_dict[video][str(frame_id)][2]]
            eye_center = [(eyes[0][0]+eyes[1][0])/2,(eyes[0][1]+eyes[1][1])/2]
        bbox_center = [(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2]
        if frame_id < len(data)*4:
            if (bbox_center[0]<nose[0] or bbox_center[0] <eye_center[0]) and np.abs(bbox_center[1]-nose[1])<100:
                if frame_id-last_right<=10*8 and frame_id-last_right>4 and last_right>=0:
                    data[int(last_right//4):int(frame_id//4), 1:] = 0.5 * data[int(last_right//4):int(frame_id//4),
                                                                         1:]
                    data[int(last_right//4):int(frame_id//4),3]=1.01
                else:
                    data[min(int(frame_id // 4), len(data)), 1:] = 0.5*data[min(int(frame_id // 4), len(data)), 1:]
                    data[min(int(frame_id // 4), len(data)), 3] = 1.01
                last_right = frame_id
            elif (bbox_center[0]>nose[0] or bbox_center[0] >eye_center[0]) and np.abs(bbox_center[1]-nose[1])<100:
                if frame_id-last_left<=10*8 and frame_id-last_left>4 and last_left>=0:
                    data[int(last_left//4):int(frame_id//4), 1:] = 0.5 * data[int(last_left//4):int(frame_id//4),1:]
                    data[int(last_left//4):int(frame_id//4),4]=1.01
                else:
                    data[min(int(frame_id // 4), len(data)), 1:] = 0.5 * data[min(int(frame_id // 4), len(data)),1:]
                    data[min(int(frame_id // 4), len(data)), 4] = 1.01
                last_left = frame_id
    return data

def add_bottle(data,video,T=False):
    """
    :param data:
    :return:
    """
    if T:
        with open(os.path.join(AICITY_DATA_ROOT,'pose','A1_pose.txt'), 'r') as f:
            poses = f.readlines()  # r'W:\aicity/aicity1/A1'
        results_root = os.path.join(AICITY_DATA_ROOT,'bottle_detect/A1')
    else:
        with open(os.path.join(AICITY_DATA_ROOT,'pose','A2_pose.txt'), 'r') as f:
            poses = f.readlines() # r'W:\aicity/aicity1/A1'
        results_root = os.path.join(AICITY_DATA_ROOT,'bottle_detect/A2')

    pose_dict = dict()

    for pose in poses:
        pose = pose.split('\n')[0]
        pose = pose.split(' ')
        videoid = pose[0]
        frame_id = pose[1]
        keypoints = [
                     [int(pose[2]), int(pose[3])],
                     [int(pose[4]), int(pose[5])],
                     [int(pose[6]), int(pose[7])],
                     [int(pose[8]), int(pose[9])],
                     [int(pose[10]), int(pose[11])]]
        if videoid not in pose_dict.keys():
            pose_dict[videoid]=dict()
        pose_dict[videoid][frame_id]=keypoints


    # print(video)
    result_file = 'modify_' + video + '_bottle_results.txt'
    with open(os.path.join(results_root,result_file),'r') as f:
        results = f.readlines()
    img = None
    last = -1
    for rst in results:
        rst = rst.split('\n')[0]
        rst = rst.split(' ')

        frame_id = int(rst[0])
        bbox = [int(x) for x in rst[1:5]]
        score = float(rst[5])
        if str(frame_id) in pose_dict[video].keys():
            nose = pose_dict[video][str(frame_id)][0]
            bbox_center = [(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2]
            # if bbox_center[0]<nose[0] and np.abs(bbox_center[1]-nose[1])<50:
            if frame_id - last <= 10*8 and frame_id-last>4:
                data[last//4:min(int(frame_id//4),len(data)),2]=1.0
            else:
                data[min(int(frame_id // 4), len(data)), 2] = 1.0
            last = frame_id
    return data

def processes_single_video_id_enforced(results_root,
                                       multi_videos,
                                       pose_txt,
                                       bottle_det_dir,
                                       cellphone_det_dir,
                                       post='_latest_results_halfs',
                                       step=4,
                                       show=False,
                                       outprint=False,gt=None):
    """
    :param results_root:
    :param multi_videos:
    :param post:
    :param step:
    :param show:
    :param outprint:
    :return:
    """
    data1=np.loadtxt(os.path.join(results_root, multi_videos[0].split('.')[0])+post[0]+'.txt')
    data2=np.loadtxt(os.path.join(results_root, multi_videos[1].split('.')[0])+post[1]+'.txt')
    data3=np.loadtxt(os.path.join(results_root, multi_videos[2].split('.')[0])+post[2]+'.txt')
    zhy_stamps=np.loadtxt(os.path.join(results_root,'stamp_results','bbox1', multi_videos[2][-27:-4]+'.txt'),delimiter=',')
    # score_mask1 = np.array([[1, 1,1,1,1, 1,0,0,0, 0,0,0,0, 1,1,1,0, 1,1]])
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,1, 1,1,0,0, 0,1,1,1, 0,1]])
    # score_mask3 = np.array([[1, 0,1,1,1, 1,1,1,1, 1,1,1,1, 0,1,0,0, 0,1]])
    # score_mask1 = np.array([[1, 1,1,0,0, 1,0,0,0, 0,0,0,0, 1,1,1,0, 1,1]])
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,1, 1,1,0,0, 0,1,1,1, 0,1]])
    # score_mask3 = np.array([[1, 0,0,1,1, 1,1,1,1, 1,1,1,1, 0,1,0,0, 0,1]])
    score_mask1 = np.array([[1, 1,1,1,1, 1,0,0,0, 0,0,0,0, 1,1,1,0, 0,0]])#
    score_mask2 = np.array([[1, 0,0,0,0, 1,1,0,0, 1,1,0,0, 0,1,1,1, 0,0]])#
    score_mask3 = np.array([[1, 0,0,1,1, 0,1,1,1, 1,1,1,1, 0,1,0,0, 0,0]])#
    # score_mask1 = np.array([[1, 1,1,1,1, 1,0,0,0, 0,0,0,0, 1,1,0,0, 0,0]])#
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,0, 1,1,0,0, 0,1,0,1, 0,0]])#
    # score_mask3 = np.array([[1, 0,0,1,1, 0,1,1,1, 1,1,1,1, 0,1,0,0, 0,0]])#
    data1 = data1 * score_mask1
    data2 = data2 * score_mask2
    data3 = data3 * score_mask3

    # CLASSES = list(range(1, len(Index_Action) + 1))
    N_f = min(len(data1),len(data2),len(data3))
    labels=None
    if gt is not None:
        labels=np.zeros(N_f,dtype='int64')
        time_stamps=dict()
        for gti in gt:
            labels[int(gti[1]*8//4):int(gti[2]*8//4)]=int(gti[0])
            time_stamps[CLASSES[int(gti[0])]]=[gti[1],gti[2]]
    data = np.stack([data1[0:N_f], data2[0:N_f], data3[0:N_f]], axis=0).max(axis=0)#data3[0:N_f]
    for i in range(data.shape[1] - 1):
        if np.sort(data[:, i + 1])[-20:].mean() < 0.4:
            data[:, i + 1] = data[:, i + 1] / (data[:, i + 1].max() + 0.001)
            data[:, i + 1] = np.convolve(data[:, i + 1], np.ones(7) / 7, 1)
    data = add_cellphone(data, multi_videos[0].split('.MP4')[0])
    data = add_bottle(data, multi_videos[0].split('.MP4')[0])
    #begin
    scores = []
    for stamp in zhy_stamps:
        scores.append(data[int(stamp[0]*8//4):int(stamp[1]*8//4),1:].mean(axis=0))
    scores = np.array(scores)
    all_proposals=dict()
    proposals=[]
    score_map = np.zeros((18,len(zhy_stamps)))
    for ind in range(len(zhy_stamps)):
        proposals.append([[np.array([int(zhy_stamps[ind][0] * 8), -1,
                                            0]),
                                     np.array([int(zhy_stamps[ind][1] * 8), -1,
                                            0])]])
        score_map[:,ind] = data[int(zhy_stamps[ind][0] * 8 // 4):int(zhy_stamps[ind][1] * 8 // 4),1:].mean(axis=0)
    for ind in range(len(zhy_stamps)):
        ij=np.argmax(score_map)

        i,j = ij//18,ij%18
        print(score_map[i, j])
        # if score_map[i, j] <=0.3:
        #     continue
        start = proposals[j][0][0][0]
        end = proposals[j][0][-1][0]
        score=data[int(start//4):int(end//4),i+1].mean()
        all_proposals[CLASSES[i]]=[[np.array([start,i,score]),np.array([end,i,score])]]


        score_map[:,j] *= 0.5
        score_map[i, :] *= 0.5


    filtered_proposals = all_proposals
    #end
    stamps = data[:,1]>data[:,1].mean()
    # stamps= stamps[0:-1]^stamps[1:]
    # idxs = np.where(stamps)
    # for i in range(len(idxs)-1):
    #     if idxs[i+1]-idxs[i]>
    # show_time_bar(all_proposals, labels, step=step, N_f=N_f, video=multi_videos[0])
    result = np.vstack([data[:,0],np.argmax(data[:,1:-2],axis=1),np.max(data[:,1:-2],axis=1)]).transpose()

    # primary link
    all_proposals = link_tubes(data, MAX_INTERRUPTION = 4)#0.8

    show_time_bar(all_proposals, labels, step=step, N_f=N_f, video=multi_videos[0])
    # second link
    all_proposals = post_link(all_proposals, max_interp_time=8, min_const_time=14, max_const_time=28)###TODO
    cnt=0
    for x in all_proposals[CLASSES[2]]:
        if len(x)>3:
            cnt+=1
    if cnt > 10:
        print("{:s} will use new parameters...._________________{:d}".format(multi_videos[0],cnt))
        for i in range(data.shape[1] - 1):
            # if np.sort(data[:, i + 1])[-20:].mean() < 0.4:
            data[:, i + 1] = data[:, i + 1] / (data[:, i + 1].max() + 0.001)
            data[:, i + 1] = np.convolve(data[:, i + 1], np.ones(7) / 7, 1)
        all_proposals = link_tubes(data, MAX_INTERRUPTION=4)
        all_proposals = post_link(all_proposals, max_interp_time=8, min_const_time=14, max_const_time=28)  ###TODO

    all_proposals = modify_margin(all_proposals, data, zhy_stamps, step)
    # filtered_proposals =all_proposals
    filtered_proposals = filter_proposals(all_proposals,
                     min_const_time=[10, 32],
                     TOP_K=5)
    show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=multi_videos[0], mark=False)

    # show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=multi_videos[0], mark=False)
    filtered_proposals = cascade_filter(filtered_proposals, data, None, step, pwm_th=0.30, min_const_time=10,
                                        max_const_time=32)  # 8
    filtered_proposals = filter_proposals(filtered_proposals,
                     min_const_time=[14, 32],
                     TOP_K=1)
    filtered_proposals=filter_multi_out(filtered_proposals, N_f)
    show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=multi_videos[0],mark=True)
    if show:
        show_time_bar(filtered_proposals, step=step, N_f=N_f)

    if outprint:
        correct=0
        count = 0
        bar=np.zeros(len(data))
        print("\nFiltered results are as following...\n")
        for clsname in CLASSES:
            if clsname not in filtered_proposals.keys() or clsname.startswith('0:'):
                continue
            for i, proposal in enumerate(filtered_proposals[clsname]):
                array_proposal = np.array(proposal)
                out = [array_proposal[0][0], array_proposal[-1][0], array_proposal[:, 2].mean(),i,len(proposal)*step]
                print(
                    "{:s}-{:d}: {:03d}:{:03d}, {:02d}:{:02d}.{:02d}--{:02d}:{:02d}.{:02d}, {:02d}:{:02d}.{:02d}, {:.4f},  {:d}/{:d}".format(
                        clsname, i, int(out[0]), int(out[1]),
                        int(out[0] / 8 // 60),
                        int(out[0] / 8 % 60),
                        int((out[0] / 8 % 60 - int(out[0] / 8 % 60)) * 100),
                        int(out[1] / 8 // 60),
                        int(out[1] / 8 % 60),
                        int((out[1] / 8 % 60 - int(out[1] / 8 % 60)) * 100),
                        int((out[1] - out[0]) / 8 // 60),
                        int((out[1] - out[0]) / 8 % 60),
                        int(((out[1] - out[0]) / 8 % 60 - int(
                            (out[1] - out[0]) / 8 % 60)) * 100),
                        out[2], len(proposal)*step+16,
                        int(out[1] - out[0])))
    return filtered_proposals,data
import csv
def test_one():
    ###test
    step=4
    interp=20#
    show=False
    outprint=True
    video = 'User_id_49381_0'
    data1 = np.loadtxt(
        r'G:\lessons\data\AICityTrack3\AICityTrack3\2022\data_result\val49831\Dashboard_'+video+'_latest_results_4.txt')#Rightside_window_User_id_35133_0_results
    data2 = np.loadtxt(
        r'G:\lessons\data\AICityTrack3\AICityTrack3\2022\data_result\val49831\Rear_view_'+video+'_best_top1_acc_epoch_1_results_4.txt')  # Rightside_window_User_id_35133_0_results
    data3 = np.loadtxt(
        r'G:\lessons\data\AICityTrack3\AICityTrack3\2022\data_result\val49831\Right_side_window_'+video+'_best_top1_acc_epoch_5_results_4.txt')  # Rightside_window_User_id_35133_0_results
    N_f = min(len(data1), len(data2), len(data3))  # clip number
    labels, mask, time_stamps = load_gt(step, r'W:\aicity\aicity1\A1\labels.json', 'Right_side_window_'+video, N_f, 18)
    zhy_stamps = np.loadtxt(os.path.join(r'G:\lessons\data\AICityTrack3\AICityTrack3\2022\data_result\val49831', 'stamps', video[-27:] + '.txt'),
                            delimiter=',')
    # out = post_zhyNMS(data[:,1:19], step, interp, threshold_ratio=0.1, score_threshold=0.25, MIN_LENGTH=5)

    # for clsname in CLASSES[1:]:
    #     print("{:s}:".format(clsname))
    #     if clsname in out.keys():
    #         print(out[clsname])
    #     else:
    #         print("\n")

    # score_mask1 = np.array([[1, 1,1,1,1, 0,0,1,1, 0,0,0,1, 1,1,1,0, 1,1]])
    # score_mask2 = np.array([[1, 1,0,0,0, 0,1,0,0, 1,0,0,0, 1,0,0,0, 0,1]])
    # score_mask3 = np.array([[1, 1,0,1,1, 1,0,1,0, 1,1,1,1, 0,0,0,1, 0,1]])
    # score_mask1 = np.array([[1, 1,1,1,1, 1,0,0,1, 0,0,0,0, 1,0,1,0, 1,1]])
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,0, 1,1,1,0, 0,1,1,1, 0,1]])
    # score_mask3 = np.array([[1, 0,0,1,1, 0,1,1,1, 1,1,1,1, 0,1,1,1, 0,1]])
    # score_mask1 = np.array([[1, 1,1,1,1, 0,0,0,0, 0,0,0,0, 1,1,1,0, 1,1]])#
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,1, 1,1,0,0, 0,1,1,1, 0,1]])#
    # score_mask3 = np.array([[1, 0,1,1,1, 1,1,1,1, 1,1,1,1, 0,1,0,0, 0,1]])#
    score_mask1 = np.array([[1, 1,1,1,1, 1,0,0,0, 0,0,0,0, 1,1,1,0, 0,0]])#
    score_mask2 = np.array([[1, 0,0,0,0, 1,1,0,0, 1,1,0,0, 0,1,1,1, 0,0]])#
    score_mask3 = np.array([[1, 0,0,1,1, 0,1,1,1, 1,1,1,1, 0,1,0,0, 0,0]])#
    # score_mask1 = np.array([[1, 1,1,0,0, 1,0,0,0, 0,0,0,0, 1,1,1,0, 1,1]])
    # score_mask2 = np.array([[1, 0,0,0,0, 0,1,0,1, 1,1,0,0, 0,1,1,1, 0,1]])
    # score_mask3 = np.array([[1, 0,0,1,1, 1,1,1,1, 1,1,1,1, 0,1,0,0, 0,1]])
    # print('dash')
    # mean_class_acc = mean_class_accuracy(data1[0:N_f, 1:-1][mask], labels[0:N_f][mask])
    # print('rear')
    # mean_class_acc = mean_class_accuracy(data2[0:N_f, 1:-1][mask], labels[0:N_f][mask])
    # print('right')
    # mean_class_acc = mean_class_accuracy(data3[0:N_f, 1:-1][mask], labels[0:N_f][mask])
    data1 = data1 * score_mask1
    data2 = data2 * score_mask2
    data3 = data3 * score_mask3
    data = np.stack([data1[0:N_f], data2[0:N_f], data3[0:N_f]],axis=0).max(axis=0)
    for i in range(data.shape[1] - 1):
        if np.sort(data[:, i + 1])[-20:].mean() < 0.4:
            data[:, i + 1] = data[:, i + 1] / (data[:, i + 1].max() + 0.001)
            data[:, i + 1] = np.convolve(data[:, i + 1], np.ones(7) / 7, 1)
    data = add_bottle(data,'Dashboard_'+video,True)
    data = add_cellphone(data, 'Dashboard_' + video, True)
    stamps = data[:, 1] > data[:, 1].mean()
    # plt.figure()
    # plt.plot(data[:,1]>0.8)
    # plt.plot(mask)
    # plt.title(video)
    # plt.show()
    np.savetxt(r'G:\lessons\data\AICityTrack3\AICityTrack3\2022\data_result\val49831\\'+video+'_results_4.txt',data,fmt='%.4f')

    # mean_class_acc = mean_class_accuracy(data[:,1:-1], labels[0:N_f])#3[0:N_f,1:-2]

    result = np.vstack([data[:,0],np.argmax(data[:,1:19],axis=1),np.max(data[:,1:19],axis=1)]).transpose()

    # primary link
    all_proposals = link_tubes(data, MAX_INTERRUPTION=4)  # 0.8

    show_time_bar(all_proposals, labels, step=step, N_f=N_f, video=video)
    # second link
    all_proposals = post_link(all_proposals, max_interp_time=8, min_const_time=14, max_const_time=28)  ###TODO
    # cnt = 0
    # for x in all_proposals[CLASSES[2]]:
    #     if len(x) > 3:
    #         cnt += 1
    # if cnt > 10:
    #     print("{:s} will use new parameters...._________________{:d}".format(video, cnt))
    #     for i in range(data.shape[1] - 1):
    #         # if np.sort(data[:, i + 1])[-20:].mean() < 0.4:
    #         data[:, i + 1] = data[:, i + 1] / (data[:, i + 1].max() + 0.001)
    #         data[:, i + 1] = np.convolve(data[:, i + 1], np.ones(7) / 7, 1)
    #     all_proposals = link_tubes(data, MAX_INTERRUPTION=4)
    #     all_proposals = post_link(all_proposals, max_interp_time=8, min_const_time=14, max_const_time=28)  ###TODO

    all_proposals = modify_margin(all_proposals, data, zhy_stamps, step)
    # filtered_proposals =all_proposals
    #
    # filter
    filtered_proposals = filter_proposals(all_proposals,
                                          min_const_time=[10, 32],
                                          TOP_K=5)
    show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=video, mark=False)

    # show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=multi_videos[0], mark=False)
    filtered_proposals = cascade_filter(filtered_proposals, data, None, step, pwm_th=0.20, min_const_time=10,
                                        max_const_time=32)  # 8
    filtered_proposals = filter_proposals(filtered_proposals,
                                          min_const_time=[14, 32],
                                          TOP_K=1)
    filtered_proposals = filter_multi_out(filtered_proposals, N_f)

    show_time_bar(filtered_proposals, labels, step=step, N_f=N_f, video=video,mark=True)
    mean_class_acc = mean_class_accuracy(proposals_trans(filtered_proposals, N_f), labels[0:N_f])
    if show:
        show_time_bar(filtered_proposals,labels,step=step,N_f=N_f)

    if outprint:
        print("\nFiltered results are as following...\n")
        bar = np.zeros(len(data))
        correct=0
        count = 0
        for clsname in CLASSES:
            for i, proposal in enumerate(filtered_proposals[clsname]):
                array_proposal = np.array(proposal)
                out = [array_proposal[0][0], array_proposal[-1][0], array_proposal[:, 2].mean(),i,len(proposal)*step] ###TODO 得分计算还有待完善，没有考虑中间未识别出的帧的影响
                if array_proposal[:,-1].mean()<0.9:
                    continue
                count +=1
                stamps[int(array_proposal[0][0] // 4):int(array_proposal[-1][0] // 4)] = 0
                bar[int(array_proposal[0][0] // 4):int(array_proposal[-1][0] // 4)] = 1
                if np.abs(out[0]/8-time_stamps[clsname][0]+1)<=1 and np.abs(out[1]/8-time_stamps[clsname][1]+1)<=1:
                    correct +=1
                print(
                    "{:s}-{:d}: {:03d}:{:03d}, {:02d}:{:02d}.{:02d}--{:02d}:{:02d}.{:02d}, {:02d}:{:02d}.{:02d}".format(
                        clsname, i, int(out[0]), int(out[1]),
                        int(out[0] / 8 // 60),
                        int(out[0] / 8 % 60),
                        int((out[0] / 8 % 60 - int(out[0] / 8 % 60)) * 100),
                        int(out[1] / 8 // 60),
                        int(out[1] / 8 % 60),
                        int((out[1] / 8 % 60 - int(out[1] / 8 % 60)) * 100),
                        int((out[1] - out[0]) / 8 // 60),
                        int((out[1] - out[0]) / 8 % 60),
                        int(((out[1] - out[0]) / 8 % 60 - int(
                            (out[1] - out[0]) / 8 % 60)) * 100)))
        for cls,clsname in enumerate(CLASSES):
            if cls!=0:
                for i, proposal in enumerate(filtered_proposals[clsname]):
                    array_proposal = np.array(proposal)
                    out = [array_proposal[0][0], array_proposal[-1][0]]
                    plt.figure()
                    if cls==1:
                        out_bar = data[:,cls + 1]
                        plt.plot(out_bar, label='score')
                        bar = np.zeros(len(out_bar))
                        plt.plot(labels == cls, label='gt')
                        bar[int(proposal[0][0] // 4):int(proposal[-1][0] // 4)] = 1
                        plt.plot(bar, label='pred')
                        plt.legend()
                        plt.title("{:s} {:s} {:.4f} {:d}".format(video, clsname, data[:, 1].mean(),
                                                                 int(np.abs(out[0] / 8 - time_stamps[clsname][
                                                                     0]) <= 1 and np.abs(
                                                                     out[1] / 8 - time_stamps[clsname][1]) <= 1)))
                    # else:
                    #     out_bar = data[max(0,int(proposal[0][0]//4-100)):min(len(data),int(proposal[-1][0]//4+100)),cls+1]
                    #     plt.plot(out_bar,label='score')
                    #     bar = np.zeros(len(out_bar))
                    #     plt.plot(labels[max(0,int(proposal[0][0]//4-100)):min(len(data),int(proposal[-1][0]//4+100))] == cls,label='gt')
                    #     bar[int(proposal[0][0]//4)-max(0,int(proposal[0][0]//4-100)):int(proposal[-1][0]//4)-max(0,int(proposal[0][0]//4-100))]=1
                    #     plt.plot(bar,label='pred')
                    #     plt.legend()
                    #     plt.title("{:s} {:s} {:.4f} {:d}".format(video,clsname, data[:, 1].mean(),
                    #                                              int(np.abs(out[0]/8-time_stamps[clsname][0])<=1 and np.abs(out[1]/8-time_stamps[clsname][1])<=1)))
                    plt.show()
        plt.figure()
        stamps = stamps[0:-1] ^ stamps[1:]
        stamps_c = stamps.copy()
        window = 15 * 8 // step
        # correct=0
        # count = 0
        for i in range(1, len(stamps) - window):
            if stamps[i:i + window].sum() > 2:
                indice = np.where(stamps[i:i + window] == 1)[0]
                stamps_c[i + 1 + indice[0]:i + indice[-1] - 1] = 0
        plt.plot(stamps_c,label='pred')
        plt.plot(labels>0,label='gt')
        plt.legend()
        plt.title("{:s} {:.4f} {:d}".format(video, data[:, 1].mean(), int(stamps_c.sum())))
        plt.show()
        print(0)
        # for clsname in CLASSES:
        #     for i, proposal in enumerate(filtered_proposals[clsname]):
        #         count += 1
        #         array_proposal = np.array(proposal)
        #         out = [array_proposal[0][0], array_proposal[-1][0]]
        #         left_points = np.where(stamps_c[:int(out[0] // 4 + 2)])[0]
        #         if len(left_points) > 0 and left_points[-1] < (15 * 8 // step):
        #             proposal[0][0] = (left_points[-1] + 1) * step
        #         right_points = np.where(stamps_c[int(out[1] // 4 - 2):])[0]
        #         if len(right_points) > 0 and right_points[0] < (15 * 8 // step):
        #             proposal[-1][0] = max(-8, min(right_points[0] * step - 20, 8)) + out[1]
        #             print(proposal[-1][0]-out[1])
        #         if np.abs(proposal[0][0]/8-time_stamps[clsname][0])<=1 and np.abs(proposal[-1][0]/8-time_stamps[clsname][1])<=1:
        #             correct += 1
        P=correct/count
        R=correct/17
        print("P={:.4f}\nR={:.4f}\nF1={:.4f}".format(P,R,P*R*2/(P+R)))
    return

def prepare_det(pose_txt,bottle_det_dir,cellphone_det_dir):
    # #####get bottle detection
    data_det_root=os.path.join(AICITY_DATA_ROOT,'data_detect')
    videos = os.listdir(data_det_root)
    videos = list(filter(lambda x: x.lower().startswith(("dash", "rear", "right")), videos))
    mkdir(bottle_det_dir)
    for video in tqdm(videos):
        with open(os.path.join(data_det_root, video, 'bbox_reuslts.txt'), 'r') as f:
            lines = f.readlines()
        with open(os.path.join(bottle_det_dir, video + '_bottle_results.txt'), 'w') as f:
            for line in lines:
                line = line.split('\n')[0]
                if line.startswith('/'):
                    frame_id = int(os.path.split(line)[1][5:-4])
                    result = []
                else:
                    line = line.split(',')
                    bbox = [int(x) for x in line[0:4]]
                    score = float(line[4])
                    cls = int(line[5])
                    if coco_classes[cls] in ['bottle', 'cup']:
                        result.append([frame_id] + bbox + [score] + [cls])
                        f.writelines('{:d} {:d} {:d} {:d} {:d} {:.4f} {:d}\n'.format(frame_id,
                                                                                     bbox[0],
                                                                                     bbox[1],
                                                                                     bbox[2],
                                                                                     bbox[3],
                                                                                     score,
                                                                                     cls))

    # #####get cellphone detection
    mkdir(cellphone_det_dir)
    videos = os.listdir(data_det_root)
    videos = list(filter(lambda x: x.lower().startswith(("dash", "rear", "right")), videos))
    for video in tqdm(videos):
        with open(os.path.join(data_det_root, video, 'bbox_reuslts.txt'), 'r') as f:
            lines = f.readlines()
        with open(os.path.join(cellphone_det_dir, video + '_cellphone_results.txt'), 'w') as f:
            for line in lines:
                line = line.split('\n')[0]
                if line.startswith('/'):
                    frame_id = int(os.path.split(line)[1][5:-4])
                    result = []
                else:
                    line = line.split(',')
                    bbox = [int(x) for x in line[0:4]]
                    score = float(line[4])
                    cls = int(line[5])
                    if coco_classes[cls] in ['cell phone']:
                        result.append([frame_id] + bbox + [score] + [cls])
                        f.writelines('{:d} {:d} {:d} {:d} {:d} {:.4f} {:d}\n'.format(frame_id,
                                                                                     bbox[0],
                                                                                     bbox[1],
                                                                                     bbox[2],
                                                                                     bbox[3],
                                                                                     score,
                                                                                     cls))

    ####filter bottle bbox with pose
    with open(pose_txt, 'r') as f:
        poses = f.readlines()
    pose_dict = dict()

    for pose in poses:
        pose = pose.split('\n')[0]
        pose = pose.split(' ')
        video = pose[0]
        frame_id = pose[1]
        keypoints = [
            [int(pose[2]), int(pose[3])],
            [int(pose[4]), int(pose[5])],
            [int(pose[6]), int(pose[7])],
            [int(pose[8]), int(pose[9])],
            [int(pose[10]), int(pose[11])]]
        if video not in pose_dict.keys():
            pose_dict[video] = dict()
        pose_dict[video][frame_id] = keypoints

    det_rst_root = bottle_det_dir
    results = os.listdir(det_rst_root)
    results = list(filter(lambda x: x.lower().startswith(('dash', 'rear', 'right')), results))
    for result in tqdm(results):
        video = result.split('_bottle')[0]
        det_results = np.loadtxt(os.path.join(det_rst_root, result), delimiter=' ')
        with open(os.path.join(det_rst_root, 'modify_' + result), 'w') as f:
            for det_rst in det_results:
                if str(int(det_rst[0])) in pose_dict[video].keys():
                    center = pose_dict[video][str(int(det_rst[0]))][0]
                    if ((det_rst[1] + det_rst[3]) / 2 - center[0]) ** 2 + (
                            (det_rst[2] + det_rst[4]) / 2 - center[1]) ** 2 < 450 ** 2 * 2:
                        f.writelines("{:d} {:d} {:d} {:d} {:d} {:.4f} {:d}\n".format(int(det_rst[0]), int(det_rst[1]),
                                                                                     int(det_rst[2]),
                                                                                     int(det_rst[3]), int(det_rst[4]),
                                                                                     det_rst[5],
                                                                                     int(det_rst[6])))
    ####filter cellphone bbox with pose
    with open(pose_txt, 'r') as f:
        poses = f.readlines()
    pose_dict = dict()

    for pose in poses:
        pose = pose.split('\n')[0]
        pose = pose.split(' ')
        video = pose[0]
        frame_id = pose[1]
        keypoints = [
            [int(pose[2]), int(pose[3])],
            [int(pose[4]), int(pose[5])],
            [int(pose[6]), int(pose[7])],
            [int(pose[8]), int(pose[9])],
            [int(pose[10]), int(pose[11])]]
        if video not in pose_dict.keys():
            pose_dict[video] = dict()
        pose_dict[video][frame_id] = keypoints

    det_rst_root = cellphone_det_dir
    results = os.listdir(det_rst_root)
    results = list(filter(lambda x: x.lower().startswith(('dash', 'rear', 'right')), results))
    for result in tqdm(results):
        video = result.split('_cellphone')[0]
        det_results = np.loadtxt(os.path.join(det_rst_root, result), delimiter=' ')
        with open(os.path.join(det_rst_root, 'modify_' + result), 'w') as f:
            for det_rst in det_results:
                if str(int(det_rst[0])) in pose_dict[video].keys():
                    center = pose_dict[video][str(int(det_rst[0]))][0]
                    if ((det_rst[1] + det_rst[3]) / 2 - center[0]) ** 2 + (
                            (det_rst[2] + det_rst[4]) / 2 - center[1]) ** 2 < 175 ** 2 * 2 and det_rst[5] > 0.5 and \
                            det_rst[1] > 520:  # *0.8200
                        f.writelines("{:d} {:d} {:d} {:d} {:d} {:.4f} {:d}\n".format(int(det_rst[0]), int(det_rst[1]),
                                                                                     int(det_rst[2]),
                                                                                     # det_results[det_results[:,1]>520,5].mean()*0.85
                                                                                     int(det_rst[3]), int(det_rst[4]),
                                                                                     det_rst[5],
                                                                                     int(det_rst[6])))

def parse_args():
    parser = argparse.ArgumentParser(description='Post process')
    parser.add_argument('--pose_pkl', help='pose keypoint file path')
    parser.add_argument('--recog_result_dir', help='action recognition result direction')
    parser.add_argument('--bottle_det_dir', help='bottle detection result direction')
    parser.add_argument('--cellphone_det_dir', help='cellphone detection result direction')
    parser.add_argument('--TAL_result_dir', help='temporal action localization result direction')
    args = parser.parse_args()
    return args

if __name__=="__main__":
    # test_one()
    args = parse_args()
    build_pose_txt(args.pose_pkl, args.pose_pkl[0:-4]+'.txt')
    prepare_det(args.pose_pkl[0:-4]+'.txt', args.bottle_det_dir, args.cellphone_det_dir)
    videos_info=[]
    with open(os.path.join(AICITY_DATA_ROOT,"video_ids.csv"), 'r') as f:
        f_csv = csv.reader(f)
        headers = next(f_csv)
        for row in f_csv:
            videos_info.append(row)

    results_root = args.recog_result_dir#'./Swin-transformer/Video-Swin-Transformer-master/submit_results_source'#r'H:\Competition\AiCity\swin-transformer\results'
    # post=['_latest_results_4','_best_top1_acc_epoch_1_results_4', '_best_top1_acc_epoch_5_results_4']
    post=['_latest_results_4','_latest_results_4','_latest_results_4']
    with open("results_submission.txt",'w') as f:
        print("\nWriting...\n")
        Ps=[]
        Rs=[]
        for i,multi_videos in enumerate(videos_info):

            filtered_proposals,data = processes_single_video_id_enforced(results_root,
                                                                         multi_videos[1:],
                                                                         args.pose_pkl[0:-4] + '.txt',
                                                                         args.bottle_det_dir,
                                                                         args.cellphone_det_dir,
                                                                         post=post,
                                                                         step=4,
                                                                         show=False,
                                                                         outprint=True)
            print(f"\n{multi_videos[1]} has been done...")
            for clsid, clsname in enumerate(CLASSES):
                if clsname not in filtered_proposals.keys():
                    continue
                for proposal in filtered_proposals[clsname]:
                    array_proposal = data[int(proposal[0][0]//4):int(proposal[-1][0]//4),[0,clsid+1,clsid+1]]

                    if clsid != 0 :#and array_proposal[:, -1].mean()>0.5:
                        f.writelines("{:d} {:d} {:d} {:d}\n".format(int(multi_videos[0]),
                                                                                        clsid,
                                                                                        int(proposal[0][0]/8)+1,
                                                                                        int(proposal[-1][0]/8)+1,))