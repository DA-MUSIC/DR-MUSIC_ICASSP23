import torch
import numpy as np
import scipy as sc
import matplotlib.pyplot as plt
import random
import torch.nn as nn
import warnings
import time
import mplcursors
import copy
import torch.optim as optim
from datetime import datetime
from itertools import permutations
from torch.autograd import Variable
from tqdm import tqdm
from torch.optim import lr_scheduler
from sklearn.model_selection import train_test_split

from DataLoaderCreation import *
from Signal_creation import *
from methods import *
from models import *
from EvaluationMesures import *

warnings.simplefilter("ignore")
plt.close('all')

def Set_Overall_Seed(SeedNumber = 42):
  random.seed(SeedNumber)
  np.random.seed(SeedNumber)
  torch.manual_seed(SeedNumber)

Set_Overall_Seed()
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

saving_path = r"C:\Users\dorsh\OneDrive\שולחן העבודה\My Drive\Thesis\DeepRootMUSIC\Code\Weights\Models"

def Run_Simulation(Model_Train_DataSet,
                    Model_Test_DataSet,
                    tau, N, optimizer_name, lr_val, Schedular,
                    weight_decay_val, step_size_val, gamma_val, num_epochs,
                    model_name,
                    Bsize,
                    Sys_Model,
                    ActivationVal = 0.5,
                    checkpoint_optimizer_path = None,
                    load_flag = False, loading_path = None,
                    Plot = True, DataSetModelBased = None,
                    Plot_Spectrum_flag = False,
                    saving_path = saving_path):
  
    ## Set the seed for all available random operations
    Set_Overall_Seed()
    
    ## Current date and time
    print("\n----------------------\n")

    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    dt_string_for_save = now.strftime("%d_%m_%Y_%H_%M")
    print("date and time =", dt_string)

    ############################
    ###    Compare Models    ###
    ############################

    ## Transform model-based test dataset into DataLoader Object:
    '''
    if DataSetModelBased != None:
      print("Test_DataSet", len(Model_Test_DataSet))
      DataSetModelBased = torch.utils.data.DataLoader(DataSetModelBased,
                                batch_size=1,
                                shuffle=False,
                                drop_last=False)
      
    ## Compute MUSIC and Root-MUSIC algorithms overall loss:
      MUSIC_loss = evaluate_model_based(DataSetModelBased, Sys_Model)
      # print("Root-MUSIC Test loss = {}".format(RootMUSIC_loss))
      # print("Spatial Smoothing Root-MUSIC Test loss = {}".format(SPS_RootMUSIC_loss))
      print("MUSIC Test loss = {}".format(MUSIC_loss))
      # print("Spatial Smoothing MUSIC Test loss = {}".format(SPS_MUSIC_loss))
    '''

    ############################
    ### Model initialization ###
    ############################

    # Create a model from `Deep_Root_Net`
    # model = Deep_Root_Net(tau=tau, ActivationVal=ActivationVal)                              
    model = Deep_Root_Net_AntiRectifier(tau=tau, ActivationVal=ActivationVal)                              
    # model = Deep_Root_Net_Broadband(tau=tau, ActivationVal=ActivationVal)                              
    # model = Deep_Root_Net_AntiRectifier_Extend(tau=tau, ActivationVal=ActivationVal)                              
    
    # Load it to the specified device, either gpu or cpu
    model = model.to(device)                                   
    
    ## Loading available model
    if load_flag == True:
      if torch.cuda.is_available() == False:
        model.load_state_dict(torch.load(loading_path, map_location=torch.device('cpu')))
        print("CPU")
      else:
        model.load_state_dict(torch.load(loading_path))
      print("Loaded Succesfully")
    
    ## Create an optimizer 
    if optimizer_name == "Adam":
        optimizer = optim.Adam(model.parameters(), lr=lr_val,weight_decay=weight_decay_val)
    elif optimizer_name == "SGD":
        optimizer = optim.SGD(model.parameters(), lr=lr_val)
    elif optimizer_name == "SGD Momentum":
        optimizer = optim.SGD(model.parameters(), lr=lr_val, momentum=0.9)
    if Schedular:
        lr_decay = lr_scheduler.StepLR(optimizer, step_size=step_size_val, gamma=gamma_val)

    ## Loss criterion
    criterion = PRMSELoss()                                     # Periodic rmse loss

    ############################
    ###  Data Organization   ###
    ############################

    ## Split data into Train and Validation
    Train_DataSet, Valid_DataSet = train_test_split(Model_Train_DataSet, test_size=0.1, shuffle = True)
    print("Training DataSet size", len(Train_DataSet))
    print("Validation DataSet size", len(Valid_DataSet))

    ## Transform Training Datasets into DataLoader Object    
    Train_data = torch.utils.data.DataLoader(Train_DataSet,
                                    batch_size=Bsize,
                                    shuffle=True,
                                    drop_last=False)  
    Valid_data = torch.utils.data.DataLoader(Valid_DataSet,
                                    batch_size=1,
                                    shuffle=False,
                                    drop_last=False)
    
    ## Transform Test Dataset into DataLoader Object
    print("Test_DataSet", len(Model_Test_DataSet))
    Test_data = torch.utils.data.DataLoader(Model_Test_DataSet,
                                    batch_size=1,
                                    shuffle=False,
                                    drop_last=False)
    
    ############################
    ###     Train Model      ###
    ############################

    ## Train using the "train_model" function
    model, loss_train_list, loss_valid_list = train_model(model, Train_data, Valid_data,
                 optimizer, criterion, epochs= num_epochs, model_name=model_name, scheduler=lr_decay,
                    checkpoint_path=r"C:\Users\dorsh\OneDrive\שולחן העבודה\My Drive\Thesis\\DeepRootMUSIC\Code\\Weights" + '\ckpt-{}.pk')
    
    ## Save model Best weights
    torch.save(model.state_dict(), saving_path + '\\model_' + dt_string_for_save)
    
    ############################
    ###    Evaluate Model    ###
    ############################
    print("\n--- Evaluating Stage ---\n")
    ## Plot learning and validation loss curves
    if Plot:
      plot_learning_curve(list(range(num_epochs)), loss_train_list, loss_valid_list)

    ## Compute the model Overall loss
    DeepRootTest_loss = evaluate_model(model, Test_data, criterion)
    print("Deep Root-MUSIC Test loss = {}".format(DeepRootTest_loss))
    # print("Root-MUSIC Test loss = {}".format(RootMUSIC_loss))
    # print("MUSIC Test loss = {}".format(MUSIC_loss))

    ############################
    ###   Model's spectrum   ###
    ############################
    if Plot_Spectrum_flag:
      PlotSpectrum(model)
    
    return model, loss_train_list, loss_valid_list, DeepRootTest_loss


def train_model(model, Train_data, Valid_data,
                 optimizer, criterion, epochs,
                 model_name, scheduler=None, checkpoint_path=None):
    PRINT_WEIGHTS = False
    since = time.time()
    loss_train_list = []
    loss_valid_list = []
    min_valid_loss = np.inf
    print("\n---Start Training Stage ---\n")

    for epoch in tqdm(range(epochs)):
        ## Train the model for a specific epoch
        train_length = 0
        model.train()
        Overall_train_loss = 0.0
        model = model.to(device)
        
        for i, data in enumerate(Train_data):
            Rx, DOA = data
            # print("DOA", DOA * 180 / np.pi)
            train_length += DOA.shape[0]
            Rx = Variable(Rx, requires_grad=True).to(device)
            DOA = Variable(DOA, requires_grad=True).to(device)
            
            ## Compute model DOA predictions  
            model_parameters = model(Rx, DOA.shape[1])
                                        
            # DOA_predictions = model_parameters
            DOA_predictions = model_parameters[0]

            ## Compute training loss
            train_loss = criterion(DOA_predictions, DOA)

            ## Backpropagation stage
            try:                         
              train_loss.backward()
            except RuntimeError:
              print("linalg error")
              pass

            ## perform parameter update
            optimizer.step()                                                     
            
            model.zero_grad()                                                   # reset the gradients back to zero
            Overall_train_loss += train_loss.item()                             # add the batch training loss to epoch loss

            # print("iteration loss : ",train_loss.item())
            # if i % 50 == 0:
            #   print("Iteration = {}, accumulated loss= {}".format(i+1, Overall_train_loss / (i+1)))
            
            if PRINT_WEIGHTS:
              for name, param in model.named_parameters():
                if param.grad is not None:
                  print(name, param.grad.sum())
                else:
                  print(name, param.grad)
        # print("len(Train_data)", len(Train_data))
        # print("Overall_train_loss = {}, train_length = {}".format(Overall_train_loss, train_length))
        Overall_train_loss = Overall_train_loss / train_length               # compute the epoch training loss
        loss_train_list.append(Overall_train_loss)
        if scheduler != None:
            scheduler.step()
        ## Evaluate the model for a specific epoch
        Overall_valid_loss = 0.0
        model.eval()
        valid_length = 0
        
        with torch.no_grad():                                                   # Gradients calculation isn't required for evaluation
            for i, data in enumerate(Valid_data):
                Rx, DOA = data
                valid_length += DOA.shape[0]
                Rx = Rx.to(device)
                DOA = DOA.to(device)
                model_parameters = model(Rx, DOA.shape[1])                            # Compute prediction of DOA's
                DOA_predictions = model_parameters[0]
                # DOA_predictions = model_parameters
                eval_loss = criterion(DOA_predictions, DOA)                     # Compute evaluation predictions loss
                Overall_valid_loss += eval_loss.item()                          # add the batch evaluation loss to epoch loss
            
            Overall_valid_loss = Overall_valid_loss / valid_length
            loss_valid_list.append(Overall_valid_loss)
        
        ## Report results
        print("epoch : {}/{}, Train loss = {:.6f}, Validation loss = {:.6f}".format(epoch + 1,
                         epochs, Overall_train_loss, Overall_valid_loss))                       # display the epoch training loss
        print('lr {}'.format(optimizer.param_groups[0]['lr']))
        
        ## save model weights for better validation performences
        if min_valid_loss > Overall_valid_loss:
            print(f'Validation Loss Decreased({min_valid_loss:.6f}--->{Overall_valid_loss:.6f}) \t Saving The Model')
            min_valid_loss = Overall_valid_loss
            best_epoch = epoch
            ## Saving State Dict
            best_model_wts = copy.deepcopy(model.state_dict())
            torch.save(model.state_dict(), saving_path + '\\' +  model_name)
    
    time_elapsed = time.time() - since
    # plot_learning_curve(list(range(epochs)),
    #                     loss_train_list, loss_valid_list)
    print("\n--- Training summary ---")
    print('Training complete in {:.0f}m {:.0f}s'.format( time_elapsed // 60, time_elapsed % 60))
    print('Minimal Validation loss: {:4f} at epoch {}'.format(min_valid_loss, best_epoch))

    # load best model weights
    model.load_state_dict(best_model_wts)
    torch.save(model.state_dict(), saving_path + '//' +  model_name)
    return model, loss_train_list, loss_valid_list

def plot_learning_curve(epoch_list, train_loss, Validation_loss):
    """
    Plot the learning curve.
    """
    plt.title("Learning Curve: Loss per Epoch")
    plt.plot(epoch_list, train_loss, label="Train")
    plt.plot(epoch_list, Validation_loss, label="Validation")
    plt.xlabel("Epochs")
    plt.ylabel("Loss")
    plt.legend(loc='best')
    plt.show()

def evaluate_model(model, Data, criterion):
    loss = 0.0
    model.eval()
    test_length = 0
    # minimal_signal_eig = []
    # maximal_noise_eig = []
    with torch.no_grad():                                                                   # Gradients Calculation isnt required for evaluation
        for i, data in enumerate(Data):
            Rx, DOA = data
            test_length += DOA.shape[0]
            Rx = Rx.to(device)
            DOA = DOA.to(device)
            model_parameters = model(Rx, DOA.shape[1])                            # Compute prediction of DOA's
            DOA_predictions = model_parameters[0]
            eval_loss = criterion(DOA_predictions, DOA)                                     # Compute evaluation predictions loss
            loss += eval_loss.item()                                          # add the batch evaluation loss to epoch loss  
        loss = loss / test_length
    return loss

def evaluate_hybrid_model(model_hybrid, Data, Sys_Model, model_name=None):
    # initialize parameters for evaluation
    mb = ModelBasedMethods(Sys_Model)  
    hybrid_MUSIC_loss = []
    hybrid_ESPRIT_list = []
     
    model_hybrid.eval()
    with torch.no_grad():                                                                   # Gradients Calculation isnt required for evaluation
        for i, data in enumerate(Data):
            Rx, DOA = data
            Rx = Rx.to(device)
            DOA = DOA.to(device)
            
            ## Hybrid MUSIC
            DOA_pred, Spectrum, M = mb.hybrid_MUSIC(model_hybrid, Rx, Sys_Model.scenario)
            DOA_pred = mb.angels[DOA_pred] * 180 / np.pi                                   # Convert from Radians to Degrees
            predicted_DOA = DOA_pred[:M][::-1]
            while(predicted_DOA.shape[0] < M):
              print("Cant estimate M sources - hybrid MUSIC")
              predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)   
            loss_music = PRMSE(predicted_DOA, DOA * 180 / np.pi)
            hybrid_MUSIC_loss.append(loss_music)

            ## Hybrid ESPRIT
            predicted_DOA, M = mb.esprit(X=None, HYBRID = True, model_ESPRIT=model_hybrid, Rz=Rx, scenario=Sys_Model.scenario)                                # Convert from Radians to Degrees
            while(predicted_DOA.shape[0] < M):
              print("Cant estimate M sources - hybrid ESPRIT")
              predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)   
            loss_esprit = PRMSE(predicted_DOA, DOA * 180 / np.pi)
            hybrid_ESPRIT_list.append(loss_esprit)
    
    ang = mb.angels * 180 / np.pi
    # plt.title("Normalized Spectrum of Hybrid MUSIC & SPS MUSIC vs MUSIC")
    plt.title("Normalized Spectrum of Hybrid MUSIC & MUSIC & Broadband MUSIC")
    # plt.title("Hybrid MUSIC vs MUSIC for non-ideal Scenario")
    plt.plot(ang, Spectrum / np.max(Spectrum), label="Hybrid MUSIC")
    # plt.plot(ang, Spectrum, label="Hybrid MUSIC")
    Spectrum = list(Spectrum)
    # plt.bar(np.squeeze(DOA * 180 / np.pi), [1, 1], color ='red',width = 0.3, label="True DOA")
    plt.bar(np.squeeze(DOA * 180 / np.pi), [np.max(Spectrum), np.max(Spectrum)], color ='red',width = 0.3, label="True DOA")
    plt.xlabel("Angels")
    plt.ylabel("Amplitude")
    return np.mean(hybrid_MUSIC_loss), np.mean(hybrid_ESPRIT_list)

def PRMSE(pred, DOA):
  prmse_list = []
  for p in list(permutations(pred, len(pred))):
      p = np.array(p)
      DOA = np.array(DOA)
      error = (((p - DOA) * np.pi / 180) + np.pi / 2) % np.pi - np.pi / 2
      prmse_val = (1 / np.sqrt(len(p))) * np.linalg.norm(error)
      prmse_list.append(prmse_val)
  return np.min(prmse_list)

def PMSE(pred, DOA):
  prmse_list = []
  for p in list(permutations(pred, len(pred))):
      p = np.array(p)
      DOA = np.array(DOA)
      error = (((p - DOA) * np.pi / 180) + np.pi / 2) % np.pi - np.pi / 2
      prmse_val = (1 / len(p)) * (np.linalg.norm(error) ** 2)
      prmse_list.append(prmse_val)
  return np.min(prmse_list)

def evaluate_model_based(DataSetModelBased, Sys_Model):
  RootMUSIC_list = []
  lossESPRIT_list = []
  SPS_RootMUSIC_list = []
  BB_MUSIC_list = []
  MUSIC_list = []
  SPS_MUSIC_list = []
  mb = ModelBasedMethods(Sys_Model)
  
  if Sys_Model.scenario.startswith("Broadband"):
    for i,data in enumerate(DataSetModelBased):
        X, Y = data
        X_modelbased = X[0]
        ## RootMUSIC predictions
        DOA_pred_MUSIC, BB_MUSIC_Spectrum, M = mb.broadband_MUSIC(X_modelbased)
        DOA_pred = mb.angels[DOA_pred_MUSIC] * 180 / np.pi                                   # Convert from Radians to Degrees
        predicted_DOA = DOA_pred[:M][::-1]
        
        # if algorithm cant estimate M sources, randomize angels
        while(predicted_DOA.shape[0] < M):
          # print("Cant estimate M sources - MUSIC")
          predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)
        lossMUSIC = PRMSE(predicted_DOA, Y * 180 / np.pi)
        # lossMUSIC = PMSE(predicted_DOA, Y * 180 / np.pi)
        BB_MUSIC_list.append(lossMUSIC)
        
        ## MUSIC predictions
        DOA_pred_MUSIC, MUSIC_Spectrum, M = mb.MUSIC(X_modelbased, NUM_OF_SOURCES=M, scenario=Sys_Model.scenario)
        DOA_pred = mb.angels[DOA_pred_MUSIC] * 180 / np.pi                                   # Convert from Radians to Degrees
        predicted_DOA = DOA_pred[:M][::-1]
        
        
        # if algorithm cant estimate M sources, randomize angels
        while(predicted_DOA.shape[0] < M):
          # print("Cant estimate M sources - MUSIC")
          predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)
        lossMUSIC = PRMSE(predicted_DOA, Y * 180 / np.pi)
        # lossMUSIC = PMSE(predicted_DOA, Y * 180 / np.pi)
        MUSIC_list.append(lossMUSIC)
        
        ## ESPRIT predictions
        DOA_pred_ESPRIT, M = mb.esprit(X_modelbased, NUM_OF_SOURCES=True, scenario=Sys_Model.scenario)

        # if algorithm cant estimate M sources, randomize angels
        while(DOA_pred_ESPRIT.shape[0] < M):
          print("Cant estimate M sources - ESPRIT")
          DOA_pred_ESPRIT = np.insert(DOA_pred_ESPRIT, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)        
        lossESPRIT = PRMSE(DOA_pred_ESPRIT, Y * 180 / np.pi)
        lossESPRIT_list.append(lossESPRIT)
    
    ang = mb.angels * 180 / np.pi
    # plt.plot(ang, BB_MUSIC_Spectrum, label="BB MUSIC")
    # plt.plot(ang, MUSIC_Spectrum, label="MUSIC")
    plt.plot(ang, BB_MUSIC_Spectrum / np.max(BB_MUSIC_Spectrum), label="BB MUSIC")
    plt.plot(ang, MUSIC_Spectrum / np.max(MUSIC_Spectrum), label="MUSIC")
    plt.legend()
    return np.mean(BB_MUSIC_list), np.mean(MUSIC_list), np.mean(lossESPRIT_list)

  else:
    for i,data in enumerate(DataSetModelBased):
        X, Y = data
        X_modelbased = X[0]
        ## RootMUSIC predictions
        DOA_pred_RootMUSIC, _, M, _, _ = mb.root_music(X_modelbased, NUM_OF_SOURCES=True)

        # if algorithm cant estimate M sources, randomize angels
        while(DOA_pred_RootMUSIC.shape[0] < M):
          print("Cant estimate M sources - RootMUSIC")
          DOA_pred_RootMUSIC = np.insert(DOA_pred_RootMUSIC, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)        
        lossRootMUSIC = PRMSE(DOA_pred_RootMUSIC, Y * 180 / np.pi)
        RootMUSIC_list.append(lossRootMUSIC)

        ## ESPRIT predictions
        DOA_pred_ESPRIT, M = mb.esprit(X_modelbased, NUM_OF_SOURCES=True)

        # if algorithm cant estimate M sources, randomize angels
        while(DOA_pred_RootMUSIC.shape[0] < M):
          print("Cant estimate M sources - ESPRIT")
          DOA_pred_ESPRIT = np.insert(DOA_pred_ESPRIT, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)        
        lossESPRIT = PRMSE(DOA_pred_ESPRIT, Y * 180 / np.pi)
        lossESPRIT_list.append(lossESPRIT)

        ## Spatial Smoothing RootMUSIC predictions
        DOA_pred_SPSRootMUSIC, _, M, _, _ = mb.root_music(X_modelbased, NUM_OF_SOURCES=True,
                                                                  SPS=True, sub_array_size=int(mb.N / 2) + 1)
        
        # if algorithm cant estimate M sources, randomize angels
        while(DOA_pred_SPSRootMUSIC.shape[0] < M):
          # print("Cant estimate M sources - SPSRootMUSIC")
          DOA_pred_SPSRootMUSIC = np.insert(DOA_pred_SPSRootMUSIC, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)        
        lossSPSRootMUSIC = PRMSE(DOA_pred_SPSRootMUSIC, Y * 180 / np.pi)
        # lossSPSRootMUSIC = PMSE(DOA_pred_SPSRootMUSIC, Y * 180 / np.pi)
        SPS_RootMUSIC_list.append(lossSPSRootMUSIC)
        
        ## MUSIC predictions
        DOA_pred_MUSIC, MUSIC_Spectrum, M = mb.MUSIC(X_modelbased, NUM_OF_SOURCES=M)
        DOA_pred = mb.angels[DOA_pred_MUSIC] * 180 / np.pi                                   # Convert from Radians to Degrees
        predicted_DOA = DOA_pred[:M][::-1]
        
        # if algorithm cant estimate M sources, randomize angels
        while(predicted_DOA.shape[0] < M):
          # print("Cant estimate M sources - MUSIC")
          predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)
        lossMUSIC = PRMSE(predicted_DOA, Y * 180 / np.pi)
        # lossMUSIC = PMSE(predicted_DOA, Y * 180 / np.pi)
        MUSIC_list.append(lossMUSIC)

        ## SPS MUSIC predictions
        DOA_pred_MUSIC, SPS_MUSIC_Spectrum, M = mb.MUSIC(X_modelbased, NUM_OF_SOURCES=True,
                                                          SPS=True, sub_array_size=int(mb.N / 2) + 1)
        DOA_pred = mb.angels[DOA_pred_MUSIC] * 180 / np.pi                                   # Convert from Radians to Degrees
        predicted_DOA = DOA_pred[:M][::-1]
        
        # if algorithm cant estimate M sources, randomize angels
        while(predicted_DOA.shape[0] < M):
          # print("Cant estimate M sources - SPS MUSIC")
          predicted_DOA = np.insert(predicted_DOA, 0, np.round(np.random.rand(1) *  180 ,decimals = 2) - 90.00)
        lossSPSMUSIC = PRMSE(predicted_DOA, Y * 180 / np.pi)
        # lossSPSMUSIC = PMSE(predicted_DOA, Y * 180 / np.pi)
        SPS_MUSIC_list.append(lossSPSMUSIC)
    ang = mb.angels * 180 / np.pi
    # plt.plot(ang, MUSIC_Spectrum / np.max(MUSIC_Spectrum), label="MUSIC")
    plt.plot(ang, MUSIC_Spectrum, label="MUSIC")
    # plt.plot(ang, SPS_MUSIC_Spectrum / np.max(SPS_MUSIC_Spectrum), label="SPS MUSIC")
    # plt.plot(ang, SPS_MUSIC_Spectrum / np.max(SPS_MUSIC_Spectrum), label="SPS MUSIC")
    plt.legend()
    return np.mean(RootMUSIC_list), np.mean(MUSIC_list), np.mean(SPS_RootMUSIC_list), np.mean(SPS_MUSIC_list), np.mean(lossESPRIT_list) 


def PlotSpectrum(DeepRootMUSIC, DataSet_Rx_test, DataSet_x_test, Sys_Model):
  criterion = PRMSELoss()
  Data_Set_path = r"C:\Users\dorsh\OneDrive\שולחן העבודה\My Drive\Thesis\\DeepRootMUSIC\Code\\DataSet"
  PLOT_MUSIC = True
  PLOT_ROOT_MUSIC = True
  PLOT_DeepROOT_MUSIC = True
  PLOTTING = False

  DataSet_Rx_test = torch.utils.data.DataLoader(DataSet_Rx_test,
                          batch_size=1,
                          shuffle=False,
                          drop_last=False)
  
  DataSet_x_test = torch.utils.data.DataLoader(DataSet_x_test,
                          batch_size=1,
                          shuffle=False,
                          drop_last=False)
  
  mb = ModelBasedMethods(Sys_Model)
  
  DeepRootTest_loss = evaluate_model(DeepRootMUSIC, DataSet_Rx_test, criterion)      
  print("Deep Root-MUSIC Test loss = {}".format(DeepRootTest_loss))
  
  if Sys_Model.scenario.startswith("Broadband"):
    MUSIC_loss = evaluate_model_based(DataSet_x_test, Sys_Model)
    print("BroadBand MUSIC Test loss = {}".format(MUSIC_loss))
  else:
    RootMUSIC_loss, MUSIC_loss, SPS_RootMUSIC_loss, SPS_MUSIC_loss = evaluate_model_based(DataSet_x_test, Sys_Model)
    RootMUSIC_loss, MUSIC_loss, SPS_RootMUSIC_loss, SPS_MUSIC_loss = evaluate_model_based(DataSet_x_test, Sys_Model)
    print("MUSIC Test loss = {}".format(MUSIC_loss))
    print("Root-MUSIC Test loss = {}".format(RootMUSIC_loss))
    print("Spatial Smoothing Root-MUSIC Test loss = {}".format(SPS_RootMUSIC_loss))
    print("Spatial Smoothing MUSIC Test loss = {}".format(SPS_MUSIC_loss))
  
  if PLOTTING:
    fig = plt.figure(figsize=(16, 12), dpi=80)
    print("\n--- Interpretability Stage ---\n")
    ############################
    ## model-based evaluation ##
    ############################

    for i,data in enumerate(DataSet_x_test):
        X, Y = data
        print("Real Angle:", Y * 180 / np.pi)
        X_modelbased = X[0]
        ## RootMUSIC predictions
        DOA_pred_RootMUSIC, roots, M, DOA_pred_all, roots_angels_all = mb.root_music(X_modelbased, NUM_OF_SOURCES=True)
        lossRootMUSIC = PRMSE(DOA_pred_RootMUSIC, Y * 180 / np.pi)
        print("Root-MUSIC Estimated Angle:", DOA_pred_RootMUSIC)
        print("Root-MUSIC Loss:", lossRootMUSIC)
        
        ## MUSIC predictions
        DOA_pred_MUSIC, Spectrum, M = mb.MUSIC(X_modelbased, NUM_OF_SOURCES=M)
        DOA_pred = mb.angels[DOA_pred_MUSIC] * 180 / np.pi                                   # Convert from Radians to Deegres
        predicted_DOA = DOA_pred[:M][::-1]
        lossMUSIC = PRMSE(predicted_DOA, Y * 180 / np.pi)
        print("MUSIC Estimated Angle:", DOA_pred[:M])
        print("MUSIC Loss:", lossMUSIC)
        print("\n\n")
    
    ############################
    ##  Deep Root_MUSIC eval  ##
    ############################

    DeepRootMUSIC.eval()
    with torch.no_grad():
      for i,data in enumerate(DataSet_Rx_test):
          ## DeepRootMUSIC predictions
          Rx, DOA = data
          Y_pred, DOA_all, roots_deep = DeepRootMUSIC(Rx, DOA.shape[1])
          Deep_RootMUSIC_loss = criterion(Y_pred, DOA)
          DOA_all = DOA_all.detach().numpy()
          DOA_all = np.reshape(DOA_all, DOA_all.shape[1]) * 180 / np.pi
          roots_deep = list(roots_deep.detach().numpy())
          if (Deep_RootMUSIC_loss > 0):
            print("Real Angle:", DOA * 180 / np.pi)
            print("Deep Root-MUSIC Estimated Angle:", Y_pred * 180 / np.pi)
            print("Deep Root-MUSIC Loss:", Deep_RootMUSIC_loss)
            print("\n\n")

    if PLOT_MUSIC:
        ax1 = fig.add_subplot(131)
        ax1.set_title("Classic MUSIC")
        ax1.set_xlabel("Angels of Arrivels")
        ax1.set_ylabel("Spectrum Amplitude")
        ax1.plot(mb.angels * 180 / np.pi , Spectrum)
        ax1.plot(DOA_pred[:M], Spectrum[DOA_pred_MUSIC[:M]], "x")
    
    if PLOT_ROOT_MUSIC:
        ax2 = fig.add_subplot(132, polar=True)
        ax2.set_title("Classic Root MUSIC")
        ax2.set_xlabel("Angels of Arrivels")

        DOA_info = {}
        for i in range(len(DOA_pred_all)):
            DOA_info[DOA_pred_all[i]] = abs(roots[i])
        for angle, r in DOA_info.items():
            # print("Root-MUSIC: angle={}, r={}".format(angle,r))
            ax2.plot([0,angle * np.pi / 180],[0, r],marker='o')
    
    if PLOT_DeepROOT_MUSIC:
        ax3 = fig.add_subplot(133, polar=True)
        ax3.set_title("Deep Root MUSIC")
        ax3.set_xlabel("Angels of Arrivels")

        DOA_info = {}
        for i in range(len(DOA_all)):
            DOA_info[DOA_all[i]] = abs(roots_deep[i])

        for angle, r in DOA_info.items():
            # print("Deep Root-MUSIC :angle={}, r={}".format(angle,r))
            ax3.plot([0,angle * np.pi / 180],[0, r],marker='o')

    plt.show()
  # return RootMUSIC_loss, MUSIC_loss, SPS_RootMUSIC_loss, SPS_MUSIC_loss, DeepRootTest_loss
  return MUSIC_loss