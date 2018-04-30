FROM debian:buster-slim

MAINTAINER "Kasper Revsbech" <mail@krevsbech.dk>

ENV DEBIAN_FRONTEND=noninteractive

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends openssh-server;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

RUN mkdir /var/run/sshd
RUN echo 'root:PASSWORD' | chpasswd
RUN echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

EXPOSE 2222
CMD ["/usr/sbin/sshd", "-D", "-p", "2222"]
