#### [*docker*]

## Instructions for building a custom image (based on Ubuntu or CentOS) for the NFVbench container



- Building

  *We state here that we are dealing with a 'pik' fork from the '3.6.1' release.*

  Move to the current project (repo) base directory and then type in, for example:

  - To build a Ubuntu image - this is the **default** (original) scheme 
    
    ```bash
    docker image build --squash --file docker/Dockerfile --tag "opnfv/nfvbench:3.6.1.def" .
    ```
    
    > The default image is built against the remote latest 'nfvbench' Gerrit sources (on line). It will not therefore embed the current release for the NFVbench code in this local tree. There is a inconsistency issue since the embedded T-Rex version is explicitly named in the build file.
    
  - To build a Ubuntu image against local nfvbench sources - **development**
    
    ```bash
    docker image build --squash --file docker/Dockerfile-local --tag "opnfv/nfvbench:3.6.1.pik" .
    ```
    
    > The current local 'nfvbench' local source tree is used instead of cloning the remote repo. 
    >
    > This allows for locally testing changes that have not (yet) been pushed to the upstream repo.
    
  - To build a CentOS image - **experimental**
    
    ```bash
    docker image build --squash --file docker/Dockerfile-centos --tag "opnfv/nfvbench:3.6.1.pik.centos" .
    ```
    
    > Intention was to test a possibly different behavior of the NFVbench software when dealing with some NIC drivers. The Mellanox ConnectX-5 adapter, for example, issues a message saying that it has been tested with CentOS. However, even in this latter case, we obtain better performances with a Ubuntu container...
  
  
  REMARK:
  
  By default docker images built are not optimized in size. They consist in a stack of intermediate layers. We use here the '--squash' option which produces very much smaller single layer resultant images.
  
  This option requires the experimental functions be enabled in the docker daemon configuration.  
  You can check its current status returned by the `docker version` query.  
  If needed, edit or create the **/etc/docker/daemon.json** file and add the below content to it:
  
  ```json
  { 
      "experimental": true
  } 
  ```
  
  Then restart the docker daemon with the command `sudo systemctl restart docker` 



- Exporting
  
  An image can be saved to a tar archive file, for example:
  
  ```bash
  docker image save -o /usr/local/src/opnfv_nfvbench-a.b.c.d.tar.gz opnfv/nfvbench:a.b.c.d
  ```



- Loading
  
  This archive could be loaded into another machine:
  
  ```bash
  docker image load -i /usr/local/src/opnfv_nfvbench-a.b.c.d.tar.gz
  ```
  
  That would render an **opnfv/nfvbench:a.b.c.d** image available for launching.
  
  *Archives are an alternate solution to downloading images from a remote Docker registry.*
